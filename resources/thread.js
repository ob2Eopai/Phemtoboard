var main = function () {
	var hrNodes = document.body.querySelectorAll("hr");

	for (var i = 0; i < hrNodes.length; ++i) {
		var postNode = document.createElement("div");

		var headerNode = document.body.removeChild(hrNodes[i].nextElementSibling);
		var timeNode = headerNode.firstElementChild;
		var messageNode = document.body.removeChild(hrNodes[i].nextElementSibling);
		var footerNode = hrNodes[i].nextElementSibling;

		postNode.appendChild(headerNode);
		postNode.appendChild(messageNode);

		if (footerNode !== null && footerNode.tagName === "P") {
			document.body.removeChild(footerNode);

			var attachmentNode = footerNode.firstElementChild;

			var attachmentLink = attachmentNode.href;
			var attachmentType = attachmentNode.type;

			if (["image/jpeg", "image/png", "image/gif"].indexOf(attachmentType) !== -1) {
				var imageNode = document.createElement("img");

				imageNode.src = attachmentLink;

				attachmentNode.textContent = "";
				attachmentNode.appendChild(imageNode);

				postNode.insertBefore(attachmentNode, messageNode);
			} else if (attachmentType === "video/webm") {
				var videoNode = document.createElement("video");

				videoNode.src = attachmentLink;
				videoNode.setAttribute("controls", "");

				postNode.insertBefore(videoNode, messageNode);
			} else {
				postNode.appendChild(footerNode);
			}
		}

		document.body.insertBefore(postNode, hrNodes[i].nextSibling);
		document.body.removeChild(hrNodes[i]);
	}
};

document.addEventListener("DOMContentLoaded", main);
