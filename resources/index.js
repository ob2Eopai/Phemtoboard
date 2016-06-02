var main = function () {
	var hrNodes = document.body.querySelectorAll("hr");

	for (var i = 0; i < hrNodes.length; ++i) {
		var threadEntryNode = document.createElement("div");

		var subjectNode = document.body.removeChild(hrNodes[i].nextElementSibling);
		var descriptionNode = document.body.removeChild(hrNodes[i].nextElementSibling);

		threadEntryNode.appendChild(subjectNode);
		threadEntryNode.appendChild(descriptionNode);

		document.body.insertBefore(threadEntryNode, hrNodes[i].nextSibling);
		document.body.removeChild(hrNodes[i]);
	}
};

document.addEventListener("DOMContentLoaded", main);
