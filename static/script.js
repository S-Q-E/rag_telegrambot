document.addEventListener("DOMContentLoaded", () => {
    const uploadForm = document.getElementById("upload-form");
    const fileInput = document.getElementById("file-input");
    const assistantInput = document.getElementById("assistant-input");
    const documentsList = document.getElementById("documents-list");

    const fetchDocuments = async () => {
        const response = await fetch("/api/documents");
        const documents = await response.json();
        documentsList.innerHTML = "";
        documents.forEach(doc => {
            const li = document.createElement("li");
            li.innerHTML = `
                <span>${doc.filename} (${doc.status})</span>
                <button data-id="${doc.id}">Delete</button>
            `;
            documentsList.appendChild(li);
        });
    };

    uploadForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const formData = new FormData();
        formData.append("file", fileInput.files[0]);
        formData.append("assistant", assistantInput.value);

        await fetch("/api/documents", {
            method: "POST",
            body: formData,
        });

        fileInput.value = "";
        assistantInput.value = "";
        fetchDocuments();
    });

    documentsList.addEventListener("click", async (e) => {
        if (e.target.tagName === "BUTTON") {
            const docId = e.target.dataset.id;
            await fetch(`/api/documents/${docId}`, {
                method: "DELETE",
            });
            fetchDocuments();
        }
    });

    fetchDocuments();
});
