import { priorityClass, statusClass } from "../../tickets/constants";

export function StatusBadge({ status }) {
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${statusClass(status)}`}
    >
      {status}
    </span>
  );
}

export function PriorityBadge({ priority }) {
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${priorityClass(priority)}`}
    >
      {priority}
    </span>
  );
}
