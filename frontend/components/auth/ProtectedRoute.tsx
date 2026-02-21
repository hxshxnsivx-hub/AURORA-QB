"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth/useAuth";

interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredRole?: string;
}

export function ProtectedRoute({ children, requiredRole }: ProtectedRouteProps) {
  const router = useRouter();
  const { user, isAuthenticated } = useAuth();

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/login");
      return;
    }

    if (requiredRole && user?.role !== requiredRole) {
      // Check role hierarchy
      const roleHierarchy: Record<string, number> = {
        Student: 1,
        Faculty: 2,
        Admin: 3,
      };

      const userLevel = roleHierarchy[user?.role || ""] || 0;
      const requiredLevel = roleHierarchy[requiredRole] || 0;

      if (userLevel < requiredLevel) {
        router.push("/dashboard");
      }
    }
  }, [isAuthenticated, user, requiredRole, router]);

  if (!isAuthenticated()) {
    return null;
  }

  if (requiredRole && user?.role !== requiredRole) {
    const roleHierarchy: Record<string, number> = {
      Student: 1,
      Faculty: 2,
      Admin: 3,
    };

    const userLevel = roleHierarchy[user?.role || ""] || 0;
    const requiredLevel = roleHierarchy[requiredRole] || 0;

    if (userLevel < requiredLevel) {
      return null;
    }
  }

  return <>{children}</>;
}
