// Sortable results table.
//
// The clickable part is a <button> inside each <th>, so sorting works by
// keyboard as well as mouse, and aria-sort tells a screen reader which
// column is sorted and which way.

document.addEventListener("DOMContentLoaded", function () {
  const table = document.getElementById("results-table");
  if (!table) return;

  const headers = Array.from(table.querySelectorAll("thead th"));
  const body = table.querySelector("tbody");

  headers.forEach(function (header, index) {
    const button = header.querySelector("button");
    if (!button) return;

    button.addEventListener("click", function () {
      const numeric = header.dataset.type === "number";
      const ascending = header.getAttribute("aria-sort") !== "ascending";
      const rows = Array.from(body.querySelectorAll("tr"));

      rows.sort(function (a, b) {
        const x = a.children[index].textContent.trim();
        const y = b.children[index].textContent.trim();

        if (numeric) {
          const nx = parseFloat(x);
          const ny = parseFloat(y);
          // rows with no value sort to the bottom either way
          if (isNaN(nx) && isNaN(ny)) return 0;
          if (isNaN(nx)) return 1;
          if (isNaN(ny)) return -1;
          return ascending ? nx - ny : ny - nx;
        }
        return ascending ? x.localeCompare(y) : y.localeCompare(x);
      });

      rows.forEach(function (row) { body.appendChild(row); });

      headers.forEach(function (h) { h.setAttribute("aria-sort", "none"); });
      header.setAttribute("aria-sort", ascending ? "ascending" : "descending");
    });
  });
});
