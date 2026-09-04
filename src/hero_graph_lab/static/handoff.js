const handoffDialog = document.querySelector("#handoff-dialog");
const handoffForm = document.querySelector("#handoff-form");
const handoffStatus = document.querySelector("#handoff-status");

async function handoffJson(path, options = {}) {
  const response = await fetch(path, options);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || payload.detail || "Request failed");
  return payload;
}

document.querySelector("#mission-launch").addEventListener("click", () => {
  handoffStatus.textContent = "";
  handoffDialog.showModal();
});
document.querySelector("#handoff-close").addEventListener("click", () => handoffDialog.close());
document.querySelector("#handoff-cancel").addEventListener("click", () => handoffDialog.close());

handoffForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const criteria = document.querySelector("#handoff-criteria").value.split("\n").map((item) => item.trim()).filter(Boolean);
  const commands = document.querySelector("#handoff-commands").value.split("\n").map((item) => item.trim()).filter(Boolean);
  const submit = handoffForm.querySelector("button[type=submit]");
  submit.disabled = true;
  handoffStatus.textContent = "Creating contract";
  try {
    const designGraph = structuredClone(globalThis.heroGraphLabState?.graph || {});
    const contract = await handoffJson("/api/contracts/from-design", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: document.querySelector("#handoff-title").value.trim(),
        objective: document.querySelector("#handoff-objective").value.trim(),
        acceptance_criteria: criteria,
        graph: designGraph,
      }),
    });
    const receipt = await handoffJson(`/api/contracts/${encodeURIComponent(contract.id)}/handoff`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ executor: document.querySelector("#handoff-executor").value, commands }),
    });
    handoffStatus.textContent = `HANDED_OFF · ${receipt.handoff_path}`;
  } catch (error) {
    handoffStatus.textContent = error.message;
  } finally {
    submit.disabled = false;
  }
});
