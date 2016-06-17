#!/usr/bin/python3

# Database

import sqlite3
from binascii import hexlify
from os.path import join
from imghdr import what

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

		self.attachment_file_name = join("attachments", hexlify(attachment_ID).decode() + "." + {
			"image/jpeg": "jpg",
			"image/png": "png",
			"image/gif": "gif"
		}.get(attachment_type, "bin"))

	def add_attachment(self, attachment):
		self.attachment = attachment

		attachment_type = what(None, h = attachment)

		if attachment_type in ["jpeg", "png", "gif"]:
			attachment_type = "image/" + attachment_type
		else:
			attachment_type = "application/octet-stream"

		self.add_attachment_ID_and_type(sha256(attachment).digest(), attachment_type)

class ThreadEntry():
	subject = None
	last_timestamp = None
	posts_count = None

	def __init__(self, subject, last_timestamp, posts_count):
		self.subject = subject
		self.last_timestamp = last_timestamp
		self.posts_count = posts_count

queries = {
	"initialize": None,
	"add-container": None,
	"check-container": None,
	"get-subjects": None,
	"get-thread": None,
	"list-threads": None
}

for i in queries:
	with open(join("resources", i + ".sql"), encoding = "UTF-8") as file:
		queries[i] = file.read()

class Database():
	def __init__(self):
		self.connection = sqlite3.connect("posts.sqlite3")

		self.connection.row_factory = sqlite3.Row
		self.connection.executescript(queries["initialize"])

	def add_container(self, container):
		if container.attachment is not None:
			with open(container.attachment_file_name, "wb") as file:
				file.write(container.attachment)

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

	def list_threads(self):
		for i in self.connection.execute(queries["list-threads"], ()):
			yield ThreadEntry(i["subject"], i["last_timestamp"], i["posts_count"])



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

class ConfigFormatError(Exception):
	pass

JSON_decoder = JSONDecoder()

def split_config_line(string):
	string = string.lstrip()

	while len(string) != 0:
		if string.startswith("\""):
			parts = JSON_decoder.raw_decode(string)

			yield parts[0]

			string = string[parts[1]: ]
		else:
			parts = string.split(maxsplit = 1)

			yield parts[0]

			string = parts[1] if len(parts) == 2 else ""

		string = string.lstrip()

def parse_config(config):
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

import os
import ssl
from urllib.request import urlopen
from urllib.error import URLError

class DownloadingError(Exception):
	pass

if os.name != "posix":
	context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
else:
	context = None

def download_page(page):
	try:
		page.content = urlopen(page.link, context = context).read()
	except URLError as exception:
		raise DownloadingError(exception.reason)

import re
from html.parser import HTMLParser
from urllib.parse import unquote
from os.path import normpath, commonpath, split, splitext

class PageParsingError(Exception):
	pass

cut_timestamp = re.compile("^(\\d*\\.?\\d*)")

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
					splitext(link_parts_path)[1] in [".jpg", ".jpeg", ".jpe", ".jfif", ".png", ".gif", ".webm"] and
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

	try:
		links_parser.feed(page.content.decode())
	except UnicodeDecodeError as exception:
		raise PageParsingError(kxception.reason)

	links_parser.close()

	return result

from urllib.request import Request
from hashlib import sha256

class ExtractionError(Exception):
	pass

def extract_post(container):
	request = Request(container.link)
	request.add_header("Range", "bytes=-17")

	try:
		response = urlopen(request, context = context)
		signature = response.read()


		if response.status != 206:
			raise DownloadingError()
	except (URLError, DownloadingError):
		raise Exception("Can't download file: {!r}:".format(container.link))

	try:
		if len(signature) != 17:
			raise ExtractionError()

		if not signature.endswith(b"FEMTOBOARD-01"):
			raise ExtractionError()

		expected_length = int.from_bytes(signature[: 4], "big")

		if expected_length > 0x80000082:
			raise ExtractionError()
	except ExtractionError:
		return

	request = Request(container.link)
	request.add_header("Range", "bytes=-{}".format(expected_length + len(signature)))

	try:
		response = urlopen(request, context = context)
		actual_length = int(response.headers.get("Content-Length")) - len(signature)
		content = response.read(actual_length)

		if response.status != 206:
			raise DownloadingError()
	except (URLError, ValueError, DownloadingError):
		raise Exception("Can't download file: {!r}:".format(container.link))

	try:
		if actual_length != expected_length or actual_length != len(content):
			raise ExtractionError()

		parts = content.split(b"\n", 1)
		subject = parts[0].decode()

		if len(subject) > 128:
			raise ExtractionError()

		parts = parts[1].split(b"\xff", 1)
		message = parts[0].decode()

		if len(message) > 0x40000000:
			raise ExtractionError()

		attachment = None

		if len(parts) == 2:
			attachment = parts[1]

			if len(attachment) > 0x40000000:
				raise ExtractionError()
	except (ExtractionError, UnicodeDecodeError):
		return

	container.subject = subject
	container.message = message

	if attachment is not None:
		container.add_attachment(attachment)



# Pages generation

from string import Template
from os import listdir
from base64 import urlsafe_b64encode
from os.path import exists
from html import escape
from time import strftime, gmtime

templates = {
	"thread": None,
	"post": None,
	"image": None,
	"message": None,
	"attachment": None,
	"index": None,
	"thread-entry": None
}

for i in templates:
	with open(join("resources", i + ".tpl"), encoding = "UTF-8") as file:
		templates[i] = Template(file.read())

def get_thread_file_name(subject):
	return join("threads", urlsafe_b64encode(subject.encode()).decode() + ".htm")

def list_built_threads():
	for i in listdir("threads"):
		if splitext(i)[1] == ".htm":
			yield join("threads", i)

def build_thread(subject, thread):
	with open(get_thread_file_name(subject), "w", encoding = "UTF-8") as file:
		file.write(templates["thread"].substitute(
			subject = escape(subject)
		))

		for i in thread:
			content = templates["message"].substitute(message = escape(i.message))

			if i.attachment_ID is not None:
				attachment_path = join("..", i.attachment_file_name)

				if i.attachment_type in ["image/jpeg", "image/png", "image/gif"]:
					content = templates["image"].substitute(path = escape(attachment_path)) + content
				else:
					content += templates["attachment"].substitute(path = escape(attachment_path))

			file.write(templates["post"].substitute(
				timestamp = escape(strftime("%Y-%m-%dT%H:%M:%SZ", gmtime(i.timestamp))),
				readable_timestamp = escape(strftime("%Y-%m-%d, %H:%M:%S", gmtime(i.timestamp))),
				link = escape(i.link),
				origin = escape(i.origin),
				content = content
			))

def check_built_index():
	return exists("index.htm")

def build_index(thread_entries):
	with open("index.htm", "w", encoding = "UTF-8") as file:
		file.write(templates["index"].substitute())

		for i in thread_entries:
			file.write(templates["thread-entry"].substitute(
				link = escape(get_thread_file_name(i.subject)),
				subject = escape(i.subject),
				last_timestamp = escape(strftime("%Y-%m-%dT%H:%M:%SZ", gmtime(i.last_timestamp))),
				readable_last_timestamp = escape(strftime("%Y-%m-%d, %H:%M:%S", gmtime(i.last_timestamp))),
				posts_count = i.posts_count
			))



# Refresh

database = Database()

def refresh():
	with open("search.txt", "r", encoding = "UTF-8") as file:
		pages = list(parse_config(file.read()))

	print("Links in the search list: {}".format(len(pages)))

	containers = {}

	for i in pages:
		try:
			download_page(i)
			containers.update(parse_page(i))
		except (DownloadingError, PageParsingError) as exception:
			print("Can't parse page {!r}: {}".format(i.link, exception))
			continue

		print("Page scanned: {!r}".format(i.link))

	print("Found containers: {}".format(len(containers)))

	new_containers = []

	for i in containers:
		if not database.check_container(containers[i].link):
			new_containers.append(containers[i])

	print("New containers: {}".format(len(new_containers)))

	target_threads_subjects = set()

	for i in new_containers:
		extract_post(i)
		database.add_container(i)

		if i.subject is None:
			print("Empty container: {!r}".format(i.link))
		else:
			print("Found a new post in: {!r}".format(i.link))

			target_threads_subjects.add(i.subject)

	built_threads = set(list_built_threads())

	for i in database.get_subjects():
		if get_thread_file_name(i) not in built_threads:
			target_threads_subjects.add(i)

	for i in target_threads_subjects:
		build_thread(i, database.get_thread(i))

		print("Built thread: {!r}".format(i))

	if len(target_threads_subjects) != 0 or not check_built_index():
		build_index(database.list_threads())

		print("Built index")



# Compose

from tempfile import NamedTemporaryFile
from os import walk
from random import choice
from sys import exit

def compose(result_file_name, container_file_name, subject, message_file_name, attachment_file_name):
	with open(container_file_name, "rb") as file:
		container = file.read()

	with open(message_file_name, "r", encoding = "UTF-8") as file:
		message = file.read()

	if len(subject) > 128 or "\n" in subject:
		print("Invalid subject")

		exit(1)

	subject = subject.encode()
	message = message.encode()

	if len(message) > 0x40000000:
		print("Too long message")

		exit(1)

	if attachment_file_name is not None:
		with open(attachment_file_name, "rb") as file:
			attachment = file.read()

		if len(attachment) > 0x40000000:
			print("Too long attachment")

			exit(1)
	else:
		attachment = None

	if result_file_name is None:
		result_file = NamedTemporaryFile(
			"wb",
			suffix = splitext(container_file_name)[1],
			dir = ".",
			prefix = "",
			delete = False
		)

		print("Result: {!r}".format(split(result_file.name)[1]))
	else:
		result_file = open(result_file_name, "wb")

	with result_file as file:
		file.write(container)
		file.write(subject)
		file.write(b"\n")
		file.write(message)

		length = len(subject) + 1 + len(message)

		if attachment is not None:
			file.write(b"\xff")
			file.write(attachment)

			length += 1 + len(attachment)

		file.write(length.to_bytes(4, "big"))
		file.write(b"FEMTOBOARD-01")



# Command line

from sys import argv

if len(argv) == 1:
	refresh()
else:
	arguments_parser = ArgumentParser()
	arguments_parser.add_argument("-r", "--result", action = "store")
	arguments_parser.add_argument("container", action = "store")
	arguments_parser.add_argument("subject", action = "store")
	arguments_parser.add_argument("message", action = "store")
	arguments_parser.add_argument("-a", "--attachment", action = "store")
	parsed_arguments = arguments_parser.parse_args()

	compose(
		parsed_arguments.result,
		parsed_arguments.container,
		parsed_arguments.subject,
		parsed_arguments.message,
		parsed_arguments.attachment
	)
