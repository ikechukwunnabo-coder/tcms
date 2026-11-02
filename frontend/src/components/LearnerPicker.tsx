import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getList } from "../api/client";
import type { Learner } from "../api/types";
import { useDebounced } from "../lib/hooks";
import { Input, Select } from "./ui";

export function LearnerPicker({
  value,
  onChange,
  required,
  id = "learner-picker",
}: {
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
  id?: string;
}) {
  const [search, setSearch] = useState("");
  const term = useDebounced(search, 250);
  const learners = useQuery({
    queryKey: ["learner-picker", term],
    queryFn: () =>
      getList<Learner>("/learners/", { search: term, active: true, page_size: 50 }),
    staleTime: 30_000,
  });

  const rows = learners.data?.data ?? [];
  const selected = rows.find((learner) => String(learner.id) === value);

  return (
    <div className="picker">
      <Input
        aria-label="Search learners"
        value={search}
        onChange={(event) => setSearch(event.target.value)}
        placeholder="Type a badge number or name to narrow the list"
      />
      <Select
        id={id}
        required={required}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">
          {learners.isLoading ? "Loading learners…" : `${rows.length} learners shown`}
        </option>
        {rows.map((learner) => (
          <option value={learner.id} key={learner.id}>
            {learner.badge_no} · {learner.full_name}
          </option>
        ))}
      </Select>
      {selected ? <p className="hint">Selected: {selected.full_name}</p> : null}
    </div>
  );
}
