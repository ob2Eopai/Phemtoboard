#!/usr/bin/python3

from argparse import ArgumentParser
from tempfile import NamedTemporaryFile
from os.path import splitext, join
from os import walk
from random import choice
import re

arguments_parser = ArgumentParser()
arguments_parser.add_argument("-c", "--container", action = "store")
arguments_parser.add_argument("-r", "--result", action = "store")
arguments_parser.add_argument("message", action = "store")
arguments_parser.add_argument("-a", "--attachment", action = "store")
parsed_arguments = arguments_parser.parse_args()

container_file_name = parsed_arguments.container
result_file_name = parsed_arguments.result
message_file_name = parsed_arguments.message
attachment_file_name = parsed_arguments.attachment

# Read inputs

split_message = re.compile("\A([a-zA-Z0-9,_-]{,100})\n(.*)\Z", re.M | re.S)

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

# Write result

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
