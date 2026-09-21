"use client";

import { AttributeField } from "@/lib/attributeSchema";

/**
 * Renders the extra fields a category asks for — used by both the Add/Edit
 * Product form and the Apply to Sell form (see useAttributeSchema). `values`
 * is the attributes object being built up; onChange replaces one key at a
 * time so the rest of the form's state management doesn't need to know
 * anything about individual field types.
 */
export default function DynamicAttributeFields({
  fields,
  values,
  onChange,
}: {
  fields: AttributeField[];
  values: Record<string, string | number | boolean>;
  onChange: (key: string, value: string | number | boolean) => void;
}) {
  if (fields.length === 0) return null;

  return (
    <div className="space-y-3">
      <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Category details</p>
      <div className="grid grid-cols-2 gap-3">
        {fields.map((field) => {
          const value = values[field.key];
          const commonClass =
            "border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500";

          if (field.type === "select") {
            return (
              <select
                key={field.key}
                value={(value as string) ?? ""}
                onChange={(e) => onChange(field.key, e.target.value)}
                required={field.required}
                className={commonClass}
              >
                <option value="">{field.label}{field.required ? " *" : ""}</option>
                {field.options.map((opt) => (
                  <option key={opt} value={opt}>
                    {opt}
                  </option>
                ))}
              </select>
            );
          }

          if (field.type === "boolean") {
            return (
              <label key={field.key} className="flex items-center gap-2 text-sm text-gray-700 px-1">
                <input
                  type="checkbox"
                  checked={Boolean(value)}
                  onChange={(e) => onChange(field.key, e.target.checked)}
                  className="rounded border-gray-300"
                />
                {field.label}
                {field.required && " *"}
              </label>
            );
          }

          return (
            <input
              key={field.key}
              type={field.type === "number" ? "number" : field.type === "date" ? "date" : "text"}
              placeholder={`${field.label}${field.required ? " *" : ""}`}
              value={(value as string | number) ?? ""}
              onChange={(e) =>
                onChange(field.key, field.type === "number" ? e.target.valueAsNumber || 0 : e.target.value)
              }
              required={field.required}
              className={commonClass}
            />
          );
        })}
      </div>
    </div>
  );
}
