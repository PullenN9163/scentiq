"use client";

import { Plus } from "lucide-react";
import { useId, useState } from "react";

import { Chip } from "./chip";
import styles from "./chip-picker.module.css";

/** Parse the comma-separated format the preferences form posts. */
export function parseList(value: string): string[] {
  return value.split(",").map((entry) => entry.trim()).filter(Boolean);
}

/**
 * A set of known choice chips plus "+ Add" for free text. The selection is
 * written to one hidden input as comma-separated text, the same field name
 * and format the existing preferences form posts. Saved values that are not
 * among the choices appear as chips too.
 */
export function ChipPicker({
  name,
  label,
  choices,
  defaultValue,
  onChange,
}: {
  name: string;
  label: string;
  choices: readonly string[];
  defaultValue: readonly string[];
  onChange?: (values: string[]) => void;
}) {
  const id = useId();
  const [selected, setSelected] = useState<string[]>([...defaultValue]);
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState("");
  const lower = (value: string) => value.trim().toLowerCase();
  const known = new Set(choices.map(lower));
  const extra = selected.filter((value) => !known.has(lower(value)));
  const isOn = (value: string) => selected.some((entry) => lower(entry) === lower(value));

  function update(next: string[]) {
    setSelected(next);
    onChange?.(next);
  }
  function toggle(value: string) {
    update(isOn(value) ? selected.filter((entry) => lower(entry) !== lower(value)) : [...selected, value]);
  }
  function add() {
    const value = draft.trim().replaceAll(",", " ");
    if (value && !isOn(value)) update([...selected, value]);
    setDraft("");
    setAdding(false);
  }

  return (
    <fieldset className={styles.picker}>
      <legend className={styles.legend}>{label}</legend>
      <input type="hidden" name={name} value={selected.join(", ")} />
      <div className={styles.chips}>
        {[...choices, ...extra].map((choice) => (
          <Chip key={choice} variant="choice" pressed={isOn(choice)} onClick={() => toggle(choice)}>{choice}</Chip>
        ))}
        {adding ? (
          <span className={styles.add}>
            <label htmlFor={`${id}-add`} className="sr-only">Add to {label.toLowerCase()}</label>
            <input
              id={`${id}-add`}
              autoFocus
              value={draft}
              maxLength={80}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") { event.preventDefault(); add(); }
                if (event.key === "Escape") { event.preventDefault(); setAdding(false); setDraft(""); }
              }}
              onBlur={add}
            />
          </span>
        ) : (
          <button type="button" className={styles.addButton} onClick={() => setAdding(true)} aria-label={`Add to ${label.toLowerCase()}`}>
            <Plus aria-hidden="true" />Add
          </button>
        )}
      </div>
    </fieldset>
  );
}
