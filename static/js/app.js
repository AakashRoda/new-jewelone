// Small progressive enhancements. Every rule is enforced again on the server;
// the app works with this file switched off (extra lines then need a save).
(function () {
  "use strict";

  // Stop a second click from sending the same form twice. The server also
  // refuses duplicates through the retry key.
  document.querySelectorAll("form[data-once]").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (form.dataset.sent === "1") {
        event.preventDefault();
        return;
      }
      form.dataset.sent = "1";
      form.querySelectorAll('button[type="submit"]').forEach(function (button) {
        button.disabled = true;
      });
    });
  });
  // A page restored from the back/forward cache must be usable again.
  window.addEventListener("pageshow", function () {
    document.querySelectorAll("form[data-once]").forEach(function (form) {
      delete form.dataset.sent;
      form.querySelectorAll('button[type="submit"]').forEach(function (button) {
        button.disabled = false;
      });
    });
  });

  // "Add another line" for receipt and invoice lines.
  document.querySelectorAll("[data-add-line]").forEach(function (button) {
    button.addEventListener("click", function () {
      var prefix = button.dataset.prefix;
      var total = document.getElementById("id_" + prefix + "-TOTAL_FORMS");
      var template = document.getElementById("line-template");
      var holder = document.getElementById("lines");
      if (!total || !template || !holder) return;
      var index = parseInt(total.value, 10);
      var wrapper = document.createElement("div");
      wrapper.innerHTML = template.innerHTML.replace(/__prefix__/g, String(index));
      var card = wrapper.firstElementChild;
      holder.appendChild(card);
      total.value = String(index + 1);
      var first = card.querySelector("select, input:not([type=hidden])");
      if (first) first.focus();
    });
  });

  // Dim a line that is ticked for removal.
  document.addEventListener("change", function (event) {
    var box = event.target;
    if (box.matches && box.matches('input[type="checkbox"][name$="-DELETE"]')) {
      var card = box.closest("[data-line]");
      if (card) card.classList.toggle("removed", box.checked);
    }
  });

  // Show the supplier or the karigar field to match where the goods came from.
  var source = document.getElementById("id_source_type");
  var supplier = document.getElementById("supplier-field");
  var karigar = document.getElementById("karigar-field");
  if (source && supplier && karigar) {
    var sync = function () {
      var fromKarigar = source.value === "karigar_inward";
      supplier.hidden = fromKarigar;
      karigar.hidden = !fromKarigar;
      if (fromKarigar) supplier.querySelector("select").value = "";
      else karigar.querySelector("select").value = "";
    };
    source.addEventListener("change", sync);
    sync();
  }
})();
