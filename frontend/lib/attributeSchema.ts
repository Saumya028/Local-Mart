import { useEffect, useState } from "react";
import { apiFetch } from "./apiClient";

export type AttributeField = {
  key: string;
  label: string;
  type: "text" | "number" | "select" | "boolean" | "date";
  required: boolean;
  options: string[];
};

/**
 * Fetches the extra fields a category asks for (GET /attribute-schemas,
 * public/unauthenticated — see backend/app/routers/attribute_schemas.py)
 * and re-fetches whenever `category` changes, since a different category
 * means a different field list. Returns [] while loading or for a
 * category with nothing defined — callers don't need to special-case
 * either: the dynamic section of the form just renders nothing.
 *
 * `kind` is "product" (Add/Edit Product form) or "shop" (Apply to sell
 * form) — same shape, different place it's used.
 */
export function useAttributeSchema(kind: "product" | "shop", category: string) {
  const [fields, setFields] = useState<AttributeField[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!category.trim()) {
      setFields([]);
      return;
    }
    let cancelled = false;
    setLoading(true);
    // Category is a free-text input (see ProductForm/ApplyForm) — debounce
    // so typing "Groceries" doesn't fire 10 requests, one per keystroke.
    const timer = setTimeout(() => {
      apiFetch(`/attribute-schemas/${kind}/${encodeURIComponent(category.trim())}`)
        .then((data) => {
          if (!cancelled) setFields(data.fields ?? []);
        })
        .catch(() => {
          // A category that doesn't match anything, or a transient network
          // blip, both resolve the same way: no extra fields shown. This
          // is a progressive-enhancement layer on top of the fixed form
          // fields, never something that should block the person from
          // filling in the rest of the form.
          if (!cancelled) setFields([]);
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }, 400);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [kind, category]);

  return { fields, loading };
}
