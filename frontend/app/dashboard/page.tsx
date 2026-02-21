"use client";

import { useAuth } from "@/lib/auth/useAuth";
import { RoleGuard } from "@/components/auth/RoleGuard";

export default function DashboardPage() {
  const { user } = useAuth();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
        <p className="mt-2 text-gray-600">
          Welcome back, {user?.email}! You are logged in as {user?.role}.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <RoleGuard allowedRoles={["Student"]}>
          <div className="bg-white p-6 rounded-lg shadow">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              My Attempts
            </h3>
            <p className="text-gray-600 text-sm">
              View your exam attempts and results
            </p>
            <div className="mt-4 text-3xl font-bold text-blue-600">0</div>
          </div>
        </RoleGuard>

        <RoleGuard allowedRoles={["Student"]}>
          <div className="bg-white p-6 rounded-lg shadow">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              Performance
            </h3>
            <p className="text-gray-600 text-sm">
              Track your progress and weaknesses
            </p>
            <div className="mt-4 text-3xl font-bold text-green-600">--</div>
          </div>
        </RoleGuard>

        <RoleGuard allowedRoles={["Faculty", "Admin"]}>
          <div className="bg-white p-6 rounded-lg shadow">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              Question Banks
            </h3>
            <p className="text-gray-600 text-sm">
              Manage your question banks
            </p>
            <div className="mt-4 text-3xl font-bold text-purple-600">0</div>
          </div>
        </RoleGuard>

        <RoleGuard allowedRoles={["Faculty", "Admin"]}>
          <div className="bg-white p-6 rounded-lg shadow">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              Generated Papers
            </h3>
            <p className="text-gray-600 text-sm">
              View and manage exam papers
            </p>
            <div className="mt-4 text-3xl font-bold text-orange-600">0</div>
          </div>
        </RoleGuard>

        <div className="bg-white p-6 rounded-lg shadow">
          <h3 className="text-lg font-semibold text-gray-900 mb-2">
            Subjects
          </h3>
          <p className="text-gray-600 text-sm">
            Browse available subjects
          </p>
          <div className="mt-4 text-3xl font-bold text-indigo-600">0</div>
        </div>

        <RoleGuard allowedRoles={["Admin"]}>
          <div className="bg-white p-6 rounded-lg shadow">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              Users
            </h3>
            <p className="text-gray-600 text-sm">
              Manage system users
            </p>
            <div className="mt-4 text-3xl font-bold text-red-600">0</div>
          </div>
        </RoleGuard>
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
        <h3 className="text-lg font-semibold text-blue-900 mb-2">
          Getting Started
        </h3>
        <ul className="space-y-2 text-blue-800">
          <RoleGuard allowedRoles={["Faculty", "Admin"]}>
            <li>• Upload question banks to get started</li>
            <li>• Create subjects, units, and topics</li>
            <li>• Generate exam papers with AI assistance</li>
          </RoleGuard>
          <RoleGuard allowedRoles={["Student"]}>
            <li>• Browse available subjects</li>
            <li>• Attempt practice exams</li>
            <li>• Track your performance and progress</li>
          </RoleGuard>
        </ul>
      </div>
    </div>
  );
}
