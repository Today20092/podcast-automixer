(() => {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = "Open diagnostics folder";
  button.addEventListener("click", () => window.pywebview?.api?.open_diagnostics_folder());
  document.querySelector(".rail")?.append(button);
})();
