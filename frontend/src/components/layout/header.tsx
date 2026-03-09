"use client";

const DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
const MONTHS = ["January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"];

export function Header() {
  const now = new Date();
  const dateStr = `${MONTHS[now.getMonth()]} ${now.getDate()} - ${DAYS[now.getDay()]}`;

  return (
    <header className="flex h-14 items-center border-b border-border px-6">
      <h1 className="text-lg font-semibold">
        {dateStr}
      </h1>
    </header>
  );
}
