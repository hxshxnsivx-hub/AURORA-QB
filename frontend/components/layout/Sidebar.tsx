"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth/useAuth";

interface NavItem {
  label: string;
  href: string;
  roles: string[];
}

const navItems: NavItem[] = [
  { label: "Dashboard", href: "/dashboard", roles: ["Student", "Faculty", "Admin"] },
  { label: "Subjects", href: "/subjects", roles: ["Student", "Faculty", "Admin"] },
  { label: "Question Banks", href: "/question-banks", roles: ["Faculty", "Admin"] },
  { label: "Papers", href: "/papers", roles: ["Faculty", "Admin"] },
  { label: "My Attempts", href: "/attempts", roles: ["Student"] },
  { label: "Performance", href: "/performance", roles: ["Student"] },
  { label: "Users", href: "/users", roles: ["Admin"] },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user } = useAuth();

  if (!user) return null;

  const filteredItems = navItems.filter((item) =>
    item.roles.includes(user.role)
  );

  return (
    <aside className="w-64 bg-gray-50 border-r min-h-screen p-4">
      <nav className="space-y-2">
        {filteredItems.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`block px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                isActive
                  ? "bg-blue-600 text-white"
                  : "text-gray-700 hover:bg-gray-200"
              }`}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
