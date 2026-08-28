document.addEventListener("DOMContentLoaded", function () {
  const table = document.getElementById("results-table");
  if (!table) return;

  const headers = table.querySelectorAll("thead th");

  headers.forEach(function (header, index) {
    header.addEventListener("click", function () {
      const body = table.querySelector("tbody");
      const rows = Array.from(body.querySelectorAll("tr"));
      const numeric = header.dataset.type === "number";
      const ascending = !header.classList.contains("asc");

      rows.sort(function (a, b) {
        const x = a.children[index].textContent.trim();
        const y = b.children[index].textContent.trim();

        if (numeric) {
          const nx = parseFloat(x);
          const ny = parseFloat(y);
          if (isNaN(nx) && isNaN(ny)) return 0;
          if (isNaN(nx)) return 1;
          if (isNaN(ny)) return -1;
          return ascending ? nx - ny : ny - nx;
        }
        return ascending ? x.localeCompare(y) : y.localeCompare(x);
      });

      rows.forEach(function (row) { body.appendChild(row); });

      headers.forEach(function (h) { h.classList.remove("asc", "desc"); });
      header.classList.add(ascending ? "asc" : "desc");
    });
  });
});