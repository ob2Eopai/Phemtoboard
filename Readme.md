Phemtoboard
===========

![Icon](http://s33.postimg.org/bgdkmdvhr/icon.png)

Alternative [Femtoboard](https://github.com/femtoboard/femtoboard/) implementation in Python 3.

Tested on Linux and Windows.

Install
-------

A [Python 3](https://www.python.org/) interpreter is required, but there is a self-contained [bundle](https://github.com/ob2Eopai/Phemtoboard/releases) for Windows.

Documentation
-------------

### Refresh

Run `./phemtoboard.py` or `phemtoboard.exe` to search for new posts. It will create thread files in the `threads` directory and the main page `index.htm`. Attachments will be placed into the `attachments` directory.

### Compose

To create a femtopost use the embedded generator in the index and thread pages.

Alternatively, you can call `./phemtoboard.py` or `phemtoboard.exe` with the following console line arguments:

```
-r <resulting file> <container file> <subject string> <message file> -a <attachment file>
```

You can omit the first option, and the resulting file will be placed in the current directory under a random name.

Consult with the Femtoboard specification below for information about the input formats.

### Search a new thread

To add a new thread to the searching list, add the link to the `search.txt` file. It should work for common imageboards.

The script downloads and parses the HTML documents, listed in this file, and extracts links, satisfying certain conditions:
- a link is an `a` tag with a `href` attribute, containing at least 1 `img` element (it can contain other elements, and the `img` elements may be subelements to them);
- the link points to a file in an allowed directory or its subdirectory (by default `../src`, relative to the thread);
- the file name starts with a floating point number;
- the file name extension is one of: `jpg`, `jpeg`, `jpe`, `jfif`, `png`, `gif`, `webm`;
- only HTTP and HTTPS links allowed.

Some imageboards (like 4chan and 8chan) store user uploaded files on a distinct server. In this case you should add a `-d <allowed directory>` option after the link:

```
https://8ch.net/ddt/res/3224.html -d https://media.8ch.net/ddt/src/
```

The script extracts timestamps from file names, normalizing them to billions of seconds. If the server's timezone is not UTC, add a `-z <shift in seconds>` option. Note, that the server can use different timezones for file names and dates in posts.

Since the script uses partial downloading, the server must support range requests and `Content-Length` header.

HTTPS certificate validation is skipped on Windows.

Specification
=============

Subject is a string of up to 128 characters in UTF-8, not containing new line characters.

Message is a text in UTF-8. The maximum message size is 0x40000000 bytes. It's recommended to use new line character as line separator (not combination of carriage return and new line character) and add it to the end of non-empty messages for consistence, which is important for anonimity.

Attachment is any file of maximum 0x40000000 bytes.

Container is an image or media file in JPEG, PNG, GIF or WebM format.

Femtopost is a sequence of bytes:
- container;
- subject;
- `0x0a`;
- message;
- `0xff` byte if an attachment exists;
- optional attachment;
- length of the previous 5 items, encoded as 4 big-endian bytes;
- ASCII representation of the string: `FEMTOBOARD-01`.
