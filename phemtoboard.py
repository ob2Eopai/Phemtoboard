#!/usr/bin/python3

# Type detection

from subprocess import Popen, PIPE
import os

default_type = "application/octet-stream"

try:
	import magic

	type_detector = magic.open(magic.MAGIC_MIME_TYPE)
	type_detector.load()

	detect_type = type_detector.buffer
except:
	if os.name == "posix":
		def detect_type(buffer):
			try:
				return Popen(
					["file", "-b", "--mime-type", "-"],
					stdin = PIPE,
					stdout = PIPE,
					stderr = PIPE
				).communicate(buffer)[0].decode().strip()
			except:
				return default_type
	else:
		detect_type = lambda buffer: default_type



# Database

import sqlite3
from binascii import hexlify
from os.path import join

class Container():
	link = None
	origin = None
	timestamp = None
	subject = None
	message = None
	attachment = None
	attachment_ID = None
	attachment_type = None
	attachment_file_name = None

	def __init__(self, link, origin, timestamp, subject = None, message = None):
		self.link = link
		self.origin = origin
		self.timestamp = timestamp
		self.subject = subject
		self.message = message

	def add_attachment_ID_and_type(self, attachment_ID, attachment_type):
		self.attachment_ID = attachment_ID
		self.attachment_type = attachment_type
		self.attachment_file_name = join("attachments", hexlify(attachment_ID).decode() + ".bin")

	def add_attachment(self, attachment):
		self.attachment = attachment

		self.add_attachment_ID_and_type(sha256(attachment).digest(), detect_type(attachment))

queries = {
	"initialize": open("resources/initialize.sql").read(),
	"add-container": open("resources/add-container.sql").read(),
	"check-container": open("resources/check-container.sql").read(),
	"get-subjects": open("resources/get-subjects.sql").read(),
	"get-thread": open("resources/get-thread.sql").read()
}

class Database():
	def __init__(self):
		self.connection = sqlite3.connect("posts.sqlite3")

		self.connection.row_factory = sqlite3.Row
		self.connection.executescript(queries["initialize"])

	def add_container(self, container):
		if container.attachment is not None:
			open(container.attachment_file_name, "wb").write(container.attachment)

		self.connection.execute(queries["add-container"], (
			container.link,
			container.origin,
			container.timestamp,
			container.subject,
			container.message,
			container.attachment_ID,
			container.attachment_type
		))

		self.connection.commit()

	def check_container(self, link):
		return self.connection.execute(queries["check-container"], (link, )).fetchone()[0] == 1

	def get_subjects(self):
		for i in self.connection.execute(queries["get-subjects"]):
			yield i[0]

	def get_thread(self, subject):
		for i in self.connection.execute(queries["get-thread"], (subject, )):
			container = Container(i["link"], i["origin"], i["timestamp"], i["subject"], i["message"])

			if i["attachment_ID"] is not None:
				container.add_attachment_ID_and_type(i["attachment_ID"], i["attachment_type"])

			yield container



# Configuration

from json.decoder import JSONDecoder
from argparse import ArgumentParser
from urllib.parse import urlsplit, urljoin

class Page():
	link = None
	directories = None
	directories_parts = None
	timezone = None
	content = None

	def __init__(self, link, directories, timezone):
		self.link = link
		self.directories = directories
		self.timezone = timezone

		self.directories_parts = [urlsplit(i) for i in directories]

def split_config_line(string):
	string = string.lstrip()

	while len(string) != 0:
		if string.startswith("\""):
			parts = JSON_decoder.raw_decode(string)

			assert type(parts[0]) is str

			yield parts[0]

			string = string[parts[1]: ]
		else:
			parts = string.split(maxsplit = 1)

			yield parts[0]

			string = parts[1] if len(parts) == 2 else ""

		string = string.lstrip()

def parse_config(config):
	JSON_decoder = JSONDecoder()

	arguments_parser = ArgumentParser()
	arguments_parser.add_argument("-d", "--directory", action = "append")
	arguments_parser.add_argument("-z", "--timezone", action = "store", type = int, default = 0)

	for i in config.split("\n"):
		i = i.strip()

		if len(i) == 0 or i.startswith("#"):
			continue

		parts = list(split_config_line(i))
		link = parts[0]
		parsed_arguments = arguments_parser.parse_args(parts[1: ])

		directories = parsed_arguments.directory

		if directories is None:
			directories = [urljoin(link, "../src")]

		yield Page(link, directories, parsed_arguments.timezone)



# Network

from urllib.request import urlopen

def download_page(page):
	page.content = urlopen(page.link).read()

import re
from html.parser import HTMLParser
from urllib.parse import unquote
from os.path import normpath, commonpath, split, splitext

cut_timestamp = re.compile("\A(\d*\.?\d*)", re.M)

def parse_page(page):
	result = {}

	hrefs = []

	def handle_starttag(tag, attributes):
		attributes = dict(attributes)

		if tag == "a" and "href" in attributes:
			hrefs.append(attributes["href"])
		elif tag == "img" and len(hrefs) > 0:
			link = urljoin(page.link, hrefs[-1])

			link_parts = urlsplit(link)

			for i in page.directories_parts:
				link_parts_path = normpath(unquote(link_parts.path))
				i_path = normpath(unquote(i.path))
				link_file_name = split(link_parts_path)[1]

				if (
					link_parts.scheme in ["http", "https"] and
					link_parts.scheme == i.scheme and
					link_parts.hostname == i.hostname and
					link_parts.port == i.port and
					commonpath([link_parts_path, i_path]) == i_path and
					splitext(link_parts_path)[1] in [".jpg", ".jpeg", ".jpe", ".png", ".gif", ".webm"] and
					len(link_file_name) > 0 and
					link_file_name[0].isdigit() or link_file_name[0] == "."
				):
					timestamp = int(cut_timestamp.match(link_file_name).group(1).replace(".", "")[: 19].ljust(19, "0")) / 1e9

					result[link] = Container(link, page.link, timestamp - page.timezone)

	def handle_endtag(tag):
		if tag == "a" and len(hrefs) != 0:
			hrefs.pop()

	links_parser = HTMLParser()
	links_parser.handle_starttag = handle_starttag
	links_parser.handle_endtag = handle_endtag
	links_parser.feed(page.content.decode())

	return result

from urllib.request import Request
from hashlib import sha256

split_message = re.compile("\A([a-zA-Z0-9,_-]{,100})\n(.*)\Z", re.M | re.S)

def extract_post(container):
	request = Request(container.link)
	request.add_header("Range", "bytes=-17")

	try:
		response = urlopen(request)
		signature = response.read()

		assert response.status == 206
	except:
		raise Exception("Can't download file: {}:".format(repr(container.link)))

	try:
		assert len(signature) == 17
		assert signature.endswith(b"FEMTOBOARD-01")

		expected_length = int.from_bytes(signature[: 4], "big")

		assert expected_length < 0x80000000
	except:
		return

	request = Request(container.link)
	request.add_header("Range", "bytes=-{}".format(expected_length + len(signature)))

	try:
		response = urlopen(request)
		actual_length = int(response.headers.get("Content-Length")) - len(signature)
		content = response.read(actual_length)

		assert response.status == 206
	except:
		raise Exception("Can't download file: {}:".format(repr(container.link)))

	try:
		assert actual_length == expected_length == len(content)

		parts = content.split(b"\xff", 1)
		message = parts[0].decode()

		assert len(message) < 0x40000000

		message = split_message.match(message)

		assert message is not None

		subject = message.group(1)
		message = message.group(2)
		attachment = None

		if len(parts) == 2:
			attachment = parts[1]

			assert len(attachment) < 0x40000000
	except:
		return

	container.subject = subject
	container.message = message

	if attachment is not None:
		container.add_attachment(attachment)



# Thread generation

from string import Template
from os import listdir
from html import escape
from time import strftime, gmtime

templates = {
	"thread": Template(open("resources/thread.tpl").read()),
	"post": Template(open("resources/post.tpl").read()),
	"attachment": Template(open("resources/attachment.tpl").read())
}

def list_threads():
	for i in listdir("Threads"):
		parts = splitext(i)

		if parts[1] == ".htm":
			yield parts[0]

def build_thread(subject, thread):
	file_name = join("Threads", subject + ".htm")

	file = open(file_name, "w")

	file.write(templates["thread"].substitute(
		subject = escape(subject)
	))

	for i in thread:
		file.write(templates["post"].substitute(
			time = escape(strftime("%Y-%m-%dT%H:%M:%SZ", gmtime(i.timestamp))),
			readable_time = escape(strftime("%Y-%m-%d, %H:%M:%S", gmtime(i.timestamp))),
			link = escape(i.link),
			origin = escape(i.origin),
			message = escape(i.message)
		))

		if i.attachment_ID is not None:
			file.write(templates["attachment"].substitute(
				path = escape(join("..", i.attachment_file_name)),
				type = escape(i.attachment_type)
			))

	return file_name



# Refresh

database = Database()

def refresh():
	pages = list(parse_config(open("pages.txt", "r").read()))

	print("Pages in configuration file: {}".format(len(pages)))

	containers = {}

	for i in pages:
		try:
			download_page(i)
			containers.update(parse_page(i))
		except Exception as exception:
			print("Can't parse page {}: {}".format(repr(i.link), exception))
			continue

		print("Page scanned: {}".format(repr(i.link)))

	print("Found containers: {}".format(len(containers)))

	new_containers = []

	for i in containers:
		if not database.check_container(containers[i].link):
			new_containers.append(containers[i])

	print("New containers: {}".format(len(new_containers)))

	target_threads = set()

	for i in new_containers:
		try:
			extract_post(i)
		except Exception as exception:
			print(exception)

			continue

		database.add_container(i)

		if i.subject is None:
			print("Empty container: {}".format(repr(i.link)))
		else:
			print("Found a new post in: {}".format(repr(i.link)))

			target_threads.add(i.subject)

	target_threads |= set(database.get_subjects()) - set(list_threads())

	for i in target_threads:
		thread_file_name = build_thread(i, database.get_thread(i))

		print("Built a thread: {}".format(thread_file_name))



# Compose

from tempfile import NamedTemporaryFile
from os import walk
from random import choice

def compose(container_file_name, result_file_name, message_file_name, attachment_file_name):
	if container_file_name is None:
		possible_containers = []

		for top, directories, files in walk("Containers", followlinks = True):
			for i in files:
				if splitext(i)[1] in [".jpg", ".jpeg", ".jpe", ".png", ".gif", ".webm"]:
					possible_containers.append(join(top, i))

		container_file_name = choice(possible_containers)

		print("Container: {}".format(repr(container_file_name)))

	container = open(container_file_name, "rb").read()
	message = open(message_file_name, "r").read()

	if split_message.match(message) is None:
		print("Invalid message format")

		exit(1)

	try:
		message = message.encode()
	except:
		print("Wrong message encoding")

		exit(1)

	if len(message) >= 0x40000000:
		print("Too long message")

		exit(1)

	if attachment_file_name is not None:
		attachment = open(attachment_file_name, "rb").read()

		if len(attachment) >= 0x40000000:
			print("Too long attachment")

			exit(1)
	else:
		attachment = None

	if result_file_name is None:
		result_file = NamedTemporaryFile(
			"wb",
			suffix = splitext(container_file_name)[1],
			dir = "Uploads",
			prefix = "",
			delete = False
		)

		print("Result: {}".format(repr(result_file.name)))
	else:
		result_file = open(result_file_name, "wb")

	result_file.write(container)
	result_file.write(message)

	length = len(message)

	if attachment is not None:
		result_file.write(b"\xff")
		result_file.write(attachment)

		length += 1 + len(attachment)

	result_file.write(length.to_bytes(4, "big"))
	result_file.write(b"FEMTOBOARD-01")



# Command line

from sys import argv

if len(argv) == 1:
	refresh()
else:
	arguments_parser = ArgumentParser()
	arguments_parser.add_argument("-c", "--container", action = "store")
	arguments_parser.add_argument("-r", "--result", action = "store")
	arguments_parser.add_argument("message", action = "store")
	arguments_parser.add_argument("-a", "--attachment", action = "store")
	parsed_arguments = arguments_parser.parse_args()

	compose(parsed_arguments.container, parsed_arguments.result, parsed_arguments.message, parsed_arguments.attachment)
