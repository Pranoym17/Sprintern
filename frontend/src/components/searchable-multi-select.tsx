"use client";

import { KeyboardEvent, useMemo, useRef, useState } from "react";
import { Check, ChevronDown, X } from "lucide-react";
import type { FilterOptionGroup } from "@/lib/filter-options";

type Choice = { value: string; custom: boolean; group?: string };

export function SearchableMultiSelect({
  id,
  label,
  values,
  options,
  placeholder,
  onChange,
}: {
  id: string;
  label: string;
  values: string[];
  options: readonly string[] | readonly FilterOptionGroup[];
  placeholder: string;
  onChange: (values: string[]) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const choices = useMemo<Choice[]>(() => {
    const grouped = options.length > 0 && typeof options[0] !== "string";
    const flattened = grouped
      ? (options as readonly FilterOptionGroup[]).flatMap((group) =>
          group.options.map((value) => ({ value, group: group.label })))
      : (options as readonly string[]).map((value) => ({ value, group: undefined }));
    const selected = new Set(values.map((value) => value.toLowerCase()));
    const normalized = query.trim().toLowerCase();
    const suggestions = flattened
      .filter((option) => !selected.has(option.value.toLowerCase()))
      .filter((option) => !normalized || option.value.toLowerCase().includes(normalized))
      .slice(0, 18)
      .map((option) => ({ ...option, custom: false }));
    const customValue = query.trim();
    const customAllowed = customValue
      && !selected.has(customValue.toLowerCase())
      && !flattened.some((option) => option.value.toLowerCase() === customValue.toLowerCase());
    return customAllowed
      ? [{ value: customValue, custom: true }, ...suggestions]
      : suggestions;
  }, [options, query, values]);

  function select(value: string) {
    if (values.length >= 25) return;
    const unrestricted = ["any role or field", "anywhere"];
    const normalized = value.toLowerCase();
    if (unrestricted.includes(normalized)) {
      onChange([value]);
    } else if (!values.some((item) => item.toLowerCase() === normalized)) {
      onChange([...values.filter((item) => !unrestricted.includes(item.toLowerCase())), value]);
    }
    setQuery("");
    setActiveIndex(0);
    setOpen(true);
    window.setTimeout(() => inputRef.current?.focus(), 0);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setOpen(true);
      setActiveIndex((index) => Math.min(index + 1, Math.max(choices.length - 1, 0)));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((index) => Math.max(index - 1, 0));
    } else if (event.key === "Enter" && open && choices[activeIndex]) {
      event.preventDefault();
      select(choices[activeIndex].value);
    } else if (event.key === "Escape") {
      setOpen(false);
    } else if (event.key === "Backspace" && !query && values.length) {
      onChange(values.slice(0, -1));
    }
  }

  return <div
    className="field searchable-multi-select"
    onBlur={(event) => {
      if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false);
    }}
  >
    <label htmlFor={id}>{label}</label>
    <div className="searchable-multi-select__control" onClick={() => inputRef.current?.focus()}>
      {values.map((value) => <span className="searchable-multi-select__chip" key={value}>
        {value}
        <button type="button" aria-label={`Remove ${value}`} onClick={(event) => {
          event.stopPropagation();
          onChange(values.filter((item) => item !== value));
        }}><X size={13} /></button>
      </span>)}
      <input
        ref={inputRef}
        id={id}
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={open}
        aria-controls={`${id}-options`}
        aria-activedescendant={open && choices[activeIndex] ? `${id}-option-${activeIndex}` : undefined}
        value={query}
        onFocus={() => setOpen(true)}
        onChange={(event) => { setQuery(event.target.value); setActiveIndex(0); setOpen(true); }}
        onKeyDown={handleKeyDown}
        placeholder={values.length ? "Search or add another" : placeholder}
        maxLength={100}
      />
      <ChevronDown className={open ? "open" : ""} size={17} aria-hidden="true" />
    </div>
    {open && <div className="searchable-multi-select__menu" id={`${id}-options`} role="listbox">
      {choices.length ? choices.map((choice, index) => <button
        id={`${id}-option-${index}`}
        className={index === activeIndex ? "active" : ""}
        type="button"
        role="option"
        aria-selected={false}
        key={`${choice.custom ? "custom" : "option"}-${choice.value}`}
        onMouseDown={(event) => event.preventDefault()}
        onMouseEnter={() => setActiveIndex(index)}
        onClick={() => select(choice.value)}
      >
        <span>{choice.custom ? `Add “${choice.value}”` : choice.value}</span>
        {!choice.custom && choice.group && <small>{choice.group}</small>}
        {!choice.custom && <Check size={15} aria-hidden="true" />}
      </button>) : <p>No more matching options.</p>}
    </div>}
    <span className="field__help">Search suggestions or type a custom value and press Enter.</span>
  </div>;
}
