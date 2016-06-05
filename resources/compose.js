"use strict";

var insertForm = function (callback, subject) {
	var sectionNode = document.body.appendChild(document.createElement("section"));
	var sectionSubjectNode = sectionNode.appendChild(document.createElement("h1"));

	sectionSubjectNode.textContent = subject === null ? "Create thread" : "Reply";

	var insertInput = function (inputNode, label) {
		var inputPNode = sectionNode.appendChild(document.createElement("p"));

		if (label === null) {
			return inputPNode.appendChild(inputNode);
		} else {
			var inputLabelNode = inputPNode.appendChild(document.createElement("label"));

			inputLabelNode.textContent = label;

			return inputLabelNode.appendChild(inputNode);
		}
	};

	var subjectNode = null;

	if (subject === null) {
		subjectNode = insertInput(document.createElement("input"), "Subject: ");
	}

	var messageNode = insertInput(document.createElement("textarea"), null);
	var attachmentNode = insertInput(document.createElement("input"), "Attachment: ");
	var containerNode = insertInput(document.createElement("input"), "Container: ");
	var createNode = insertInput(document.createElement("input"), null);
	var saveNode = sectionNode.appendChild(document.createElement("a"));

	attachmentNode.type = "file";
	containerNode.type = "file";
	createNode.type = "button";
	createNode.value = "Create femtopost";

	createNode.addEventListener("click", function (event) {
		generate({
			"subject": subject === null ? subjectNode.value : subject,
			"message": messageNode.value,
			"attachment": attachmentNode.files[0],
			"container": containerNode.files[0]
		}).then(function (result) {
			if (navigator.msSaveBlob !== undefined) {
				navigator.msSaveBlob(result);
			} else {
				if (saveNode.href !== "") {
					URL.revokeObjectURL(saveNode.href);
				}

				saveNode.href = URL.createObjectURL(result);
				saveNode.click();
			}
		}, function (exception) {
			alert(exception.message);
		});
	});

	var searchNode = document.createElement("a");

	searchNode.href = (subject === null ? "" : "../") + "search.txt";
	searchNode.textContent = "search.txt";

	createNode.parentNode.appendChild(document.createTextNode(" (see your "));
	createNode.parentNode.appendChild(searchNode);
	createNode.parentNode.appendChild(document.createTextNode(" to find the list of threads to upload the femtopost)"));

	saveNode.classList.add("save");
	saveNode.download = "";
};

var encodeString = function (string) {
	var result = [];

	var URIEncoded = encodeURIComponent(string);

	for (var i = 0; i < URIEncoded.length; ++i) {
		if (URIEncoded[i] == "%") {
			result.push(Number.parseInt(URIEncoded[i + 1] + URIEncoded[i + 2], 16));
			i += 2;
		} else {
			result.push(URIEncoded.charCodeAt(i));
		}
	}

	return new Uint8Array(result);
};

var readFile = function (file) {
	return new Promise(function (resolve, reject) {
		var fileReader = new FileReader();

		fileReader.addEventListener("load", function (event) {
			resolve(new Uint8Array(this.result));
		});

		fileReader.addEventListener("error", function (event) {
			reject(new Error("Can't read file"));
		});

		fileReader.readAsArrayBuffer(file);
	});
};

var encodedMarker = encodeString("FEMTOBOARD-01");

var generate = function (input) {
	return new Promise(function (resolve, reject) {
		if (/^[a-zA-Z0-9,_-]{1,100}$/.test(input.subject) !== true) {
			reject(Error("Invalid thread subject"));
		}

		var encodedSubject = encodeString(input.subject);
		var encodedMessage = encodeString(input.message === "" ? "" : input.message + "\n");

		if (encodedMessage.length >= 0x40000000) {
			reject(new Error("Too long message"));
		}

		if (input.container === undefined) {
			reject(new Error("Container not specified"));
		}

		if (["image/jpeg", "image/png", "image/gif", "video/webm"].indexOf(input.container.type) === -1) {
			reject(new Error("Wrong container type"));
		}

		var containerPromise = readFile(input.container);
		var attachmentPromise = null;

		if (input.attachment !== undefined && input.attachment !== null) { // Edge returns null
			if (input.attachment.size > 0x40000000) {
				reject(new Error("Too long attachment"));
			}

			attachmentPromise = readFile(input.attachment);
		}

		Promise.all([attachmentPromise, containerPromise]).then(function (result) {
			var encodedAttachment = result[0];
			var encodedContainer = result[1];

			var payloadLength = (
				encodedSubject.length +
				1 +
				encodedMessage.length +
				(encodedAttachment === null ? 0 : 1 + encodedAttachment.length)
			);

			var femtopost = new Uint8Array(
				encodedContainer.length +
				payloadLength +
				4 +
				encodedMarker.length
			);

			var offset = 0;

			femtopost.set(encodedContainer, offset);
			offset += encodedContainer.length;

			femtopost.set(encodedSubject, offset);
			offset += encodedSubject.length;

			femtopost[offset] = 0x0a;
			offset += 1;

			femtopost.set(encodedMessage, offset);
			offset += encodedMessage.length;

			if (encodedAttachment !== null) {
				femtopost[offset] = 0xff;
				offset += 1;

				femtopost.set(encodedAttachment, offset);
				offset += encodedAttachment.length;
			}

			femtopost[offset] = payloadLength >>> 24;
			femtopost[offset + 1] = payloadLength >>> 16 & 0xff;
			femtopost[offset + 2] = payloadLength >>> 8 & 0xff;
			femtopost[offset + 3] = payloadLength & 0xff;
			offset += 4

			femtopost.set(encodedMarker, offset);

			resolve(new Blob([femtopost], {"type": input.container.type}));
		}, function (exception) {
			reject(exception);
		});
	});
};

var main = function () {
	var subjectNode = document.querySelector("h1 + h2");

	insertForm(generate, subjectNode === null ? null : subjectNode.textContent);
};

document.addEventListener("DOMContentLoaded", main);
