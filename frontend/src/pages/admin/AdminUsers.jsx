import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Loader2,
  RefreshCw,
  Search,
  ShieldCheck,
  Trash2,
  UserCheck,
  UserX,
  Users,
  X,
} from "lucide-react";

import AdminLayout from "../../components/AdminLayout";

const API_BASE_URL = "http://127.0.0.1:8000";

function formatDate(value) {
  if (!value) return "Never";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return "—";

  return date.toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function getStoredUser() {
  try {
    return JSON.parse(localStorage.getItem("scibrain_user") || "null");
  } catch {
    return null;
  }
}

export default function AdminUsers() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [busyUserId, setBusyUserId] = useState(null);
  const [confirmUser, setConfirmUser] = useState(null);

  const currentUser = useMemo(() => getStoredUser(), []);
  const currentUserId = currentUser?.id;

  const loadUsers = useCallback(async (showLoader = true) => {
    if (showLoader) setLoading(true);

    setError("");

    try {
      const token = localStorage.getItem("scibrain_token");

      if (!token) {
        throw new Error("Your session is missing. Please sign in again.");
      }

      const response = await fetch(`${API_BASE_URL}/api/admin/users`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        if (response.status === 401 || response.status === 403) {
          throw new Error(
            "Access denied or session expired. Sign in with an administrator account."
          );
        }

        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || "Failed to load user accounts.");
      }

      const data = await response.json();

      if (!Array.isArray(data)) {
        throw new Error("The server returned an unexpected users response.");
      }

      setUsers(data);
    } catch (err) {
      setError(err.message || "Unable to connect to the server.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  const filteredUsers = useMemo(() => {
    const query = search.trim().toLowerCase();

    return users.filter((user) => {
      const matchesSearch =
        !query ||
        String(user.full_name || "").toLowerCase().includes(query) ||
        String(user.email || "").toLowerCase().includes(query) ||
        String(user.id).includes(query);

      const matchesRole =
        roleFilter === "all" || user.role === roleFilter;

      const matchesStatus =
        statusFilter === "all" ||
        (statusFilter === "active" && user.is_active) ||
        (statusFilter === "inactive" && !user.is_active);

      return matchesSearch && matchesRole && matchesStatus;
    });
  }, [users, search, roleFilter, statusFilter]);

  const summary = useMemo(
    () => ({
      total: users.length,
      active: users.filter((user) => user.is_active).length,
      inactive: users.filter((user) => !user.is_active).length,
      admins: users.filter((user) => user.role === "admin").length,
    }),
    [users]
  );

  
async function updateUserStatus(user) {
  if (String(user.id) === String(currentUserId)) {
    setError("You cannot deactivate your own administrator account.");
    return;
  }

  const requestedStatus = !user.is_active;

  setBusyUserId(user.id);
  setError("");
  setNotice("");

  try {
    const token = localStorage.getItem("scibrain_token");

    const response = await fetch(
      `${API_BASE_URL}/api/admin/users/${user.id}/status`,
      {
        method: "PATCH",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          is_active: requestedStatus,
        }),
      }
    );

    const body = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new Error(body.detail || "Failed to update account status.");
    }

    setUsers((previous) =>
      previous.map((item) =>
        String(item.id) === String(user.id)
          ? { ...item, is_active: body.is_active }
          : item
      )
    );

    setNotice(body.message || "Account status updated.");
  } catch (err) {
    setError(err.message || "Failed to update account status.");
  } finally {
    setBusyUserId(null);
  }
}


  async function deleteUser() {
    if (!confirmUser) return;

    if (String(confirmUser.id) === String(currentUserId)) {
      setError("You cannot delete your own administrator account.");
      setConfirmUser(null);
      return;
    }

    setBusyUserId(confirmUser.id);
    setError("");
    setNotice("");

    try {
      const token = localStorage.getItem("scibrain_token");

      const response = await fetch(
        `${API_BASE_URL}/api/admin/users/${confirmUser.id}`,
        {
          method: "DELETE",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      const body = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(body.detail || "Failed to delete the user.");
      }

      setUsers((previous) =>
        previous.filter(
          (item) => String(item.id) !== String(confirmUser.id)
        )
      );

      setNotice(body.message || "User deleted successfully.");
      setConfirmUser(null);
    } catch (err) {
      setError(err.message || "Failed to delete the user.");
    } finally {
      setBusyUserId(null);
    }
  }

  return (
    <AdminLayout>
      <div className="min-h-screen space-y-7 bg-transparent text-slate-100">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="mb-2 flex items-center gap-2 text-sm text-indigo-300">
              <ShieldCheck size={16} />
              Administration
              <span className="text-slate-600">/</span>
              <span className="text-slate-400">Users</span>
            </div>

            <h1 className="text-3xl font-semibold tracking-tight">
              User Management
            </h1>

            <p className="mt-2 text-sm text-slate-400">
              Manage researcher accounts and administrator access.
            </p>
          </div>

          <button
            type="button"
            onClick={() => loadUsers()}
            disabled={loading}
            className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-700 bg-slate-900/70 px-4 py-2.5 text-sm text-slate-200 transition hover:border-indigo-500/60 hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <RefreshCw
              size={16}
              className={loading ? "animate-spin" : ""}
            />
            Refresh
          </button>
        </div>

        {error && (
          <div
            role="alert"
            className="flex items-start gap-3 rounded-xl border border-red-500/25 bg-red-500/10 p-4 text-sm text-red-200"
          >
            <AlertCircle size={18} className="mt-0.5 shrink-0" />
            <div className="flex-1">{error}</div>
            <button
              type="button"
              onClick={() => setError("")}
              aria-label="Dismiss error"
              className="text-red-200/70 hover:text-red-100"
            >
              <X size={17} />
            </button>
          </div>
        )}

        {notice && (
          <div
            role="status"
            className="flex items-start gap-3 rounded-xl border border-emerald-500/25 bg-emerald-500/10 p-4 text-sm text-emerald-200"
          >
            <CheckCircle2 size={18} className="shrink-0" />
            <div className="flex-1">{notice}</div>
            <button
              type="button"
              onClick={() => setNotice("")}
              aria-label="Dismiss notification"
              className="text-emerald-200/70 hover:text-emerald-100"
            >
              <X size={17} />
            </button>
          </div>
        )}

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {[
            {
              label: "Total Users",
              value: summary.total,
              icon: Users,
              iconStyle: "bg-indigo-500/10 text-indigo-300",
            },
            {
              label: "Active Accounts",
              value: summary.active,
              icon: UserCheck,
              iconStyle: "bg-emerald-500/10 text-emerald-300",
            },
            {
              label: "Inactive Accounts",
              value: summary.inactive,
              icon: UserX,
              iconStyle: "bg-amber-500/10 text-amber-300",
            },
            {
              label: "Administrators",
              value: summary.admins,
              icon: ShieldCheck,
              iconStyle: "bg-cyan-500/10 text-cyan-300",
            },
          ].map((stat) => {
            const Icon = stat.icon;

            return (
              <div
                key={stat.label}
                className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm text-slate-400">
                    {stat.label}
                  </span>
                  <span className={`rounded-xl p-2.5 ${stat.iconStyle}`}>
                    <Icon size={19} />
                  </span>
                </div>

                <div className="mt-4 text-3xl font-semibold tabular-nums">
                  {loading ? "—" : stat.value}
                </div>
              </div>
            );
          })}
        </div>

        <section className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/60">
          <div className="border-b border-slate-800 p-5">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
              <div>
                <h2 className="text-lg font-semibold">Registered Accounts</h2>
                <p className="mt-1 text-sm text-slate-400">
                  {filteredUsers.length} of {users.length} accounts
                </p>
              </div>

              <div className="flex flex-col gap-3 sm:flex-row">
                <div className="relative min-w-0 sm:w-64">
                  <Search
                    size={17}
                    className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500"
                  />
                  <input
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    placeholder="Search name, email, or ID..."
                    aria-label="Search users"
                    className="w-full rounded-xl border border-slate-700 bg-slate-950/70 py-2.5 pl-9 pr-3 text-sm outline-none placeholder:text-slate-600 focus:border-indigo-500"
                  />
                </div>

                <select
                  value={roleFilter}
                  onChange={(event) => setRoleFilter(event.target.value)}
                  aria-label="Filter by role"
                  className="rounded-xl border border-slate-700 bg-slate-950/70 px-3 py-2.5 text-sm text-slate-300 outline-none focus:border-indigo-500"
                >
                  <option value="all">All roles</option>
                  <option value="researcher">Researchers</option>
                  <option value="admin">Administrators</option>
                </select>

                <select
                  value={statusFilter}
                  onChange={(event) => setStatusFilter(event.target.value)}
                  aria-label="Filter by account status"
                  className="rounded-xl border border-slate-700 bg-slate-950/70 px-3 py-2.5 text-sm text-slate-300 outline-none focus:border-indigo-500"
                >
                  <option value="all">All statuses</option>
                  <option value="active">Active</option>
                  <option value="inactive">Inactive</option>
                </select>
              </div>
            </div>
          </div>

          {loading && users.length === 0 ? (
            <div className="flex min-h-64 flex-col items-center justify-center gap-3 text-slate-400">
              <Loader2 size={27} className="animate-spin text-indigo-400" />
              <p className="text-sm">Loading user accounts...</p>
            </div>
          ) : filteredUsers.length === 0 ? (
            <div className="flex min-h-64 flex-col items-center justify-center px-6 text-center">
              <Users size={30} className="text-slate-600" />
              <h3 className="mt-4 font-medium text-slate-300">
                {users.length === 0
                  ? "No registered users"
                  : "No matching users"}
              </h3>
              <p className="mt-2 max-w-sm text-sm text-slate-500">
                {users.length === 0
                  ? "User accounts will appear here when available."
                  : "Try changing your search or filters."}
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[900px] text-left text-sm">
                <thead className="bg-slate-950/60 text-xs uppercase tracking-wider text-slate-500">
                  <tr>
                    <th className="px-5 py-4 font-medium">User</th>
                    <th className="px-5 py-4 font-medium">Role</th>
                    <th className="px-5 py-4 font-medium">Status</th>
                    <th className="px-5 py-4 font-medium">Joined</th>
                    <th className="px-5 py-4 font-medium">Last Login</th>
                    <th className="px-5 py-4 text-right font-medium">
                      Actions
                    </th>
                  </tr>
                </thead>

                <tbody className="divide-y divide-slate-800/80">
                  {filteredUsers.map((user) => {
                    const isSelf =
                      String(user.id) === String(currentUserId);
                    const isBusy = busyUserId === user.id;

                    return (
                      <tr
                        key={user.id}
                        className="transition hover:bg-slate-800/30"
                      >
                        <td className="px-5 py-4">
                          <div className="flex items-center gap-3">
                            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-indigo-400/20 bg-indigo-500/10 font-semibold text-indigo-200">
                              {(user.full_name || "?")
                                .trim()
                                .charAt(0)
                                .toUpperCase()}
                            </div>

                            <div className="min-w-0">
                              <div className="flex items-center gap-2 font-medium text-slate-200">
                                <span className="truncate">
                                  {user.full_name || "Unnamed user"}
                                </span>
                                {isSelf && (
                                  <span className="shrink-0 rounded-md border border-indigo-400/20 bg-indigo-500/10 px-1.5 py-0.5 text-[10px] text-indigo-300">
                                    YOU
                                  </span>
                                )}
                              </div>
                              <div className="mt-1 truncate text-xs text-slate-500">
                                {user.email}
                              </div>
                              <div className="mt-1 text-xs text-slate-600">
                                ID: {user.id}
                              </div>
                            </div>
                          </div>
                        </td>

                        <td className="px-5 py-4">
                          <span
                            className={`inline-flex rounded-lg border px-2.5 py-1 text-xs font-medium ${
                              user.role === "admin"
                                ? "border-violet-400/20 bg-violet-500/10 text-violet-300"
                                : "border-slate-700 bg-slate-800/70 text-slate-300"
                            }`}
                          >
                            {user.role || "researcher"}
                          </span>
                        </td>

                        <td className="px-5 py-4">
                          <span
                            className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs ${
                              user.is_active
                                ? "border-emerald-400/20 bg-emerald-500/10 text-emerald-300"
                                : "border-amber-400/20 bg-amber-500/10 text-amber-300"
                            }`}
                          >
                            <span
                              className={`h-1.5 w-1.5 rounded-full ${
                                user.is_active
                                  ? "bg-emerald-400"
                                  : "bg-amber-400"
                              }`}
                            />
                            {user.is_active ? "Active" : "Inactive"}
                          </span>
                        </td>

                        <td className="px-5 py-4 text-slate-400">
                          {formatDate(user.created_at)}
                        </td>

                        <td className="px-5 py-4 text-slate-400">
                          {formatDate(user.last_login)}
                        </td>

                        <td className="px-5 py-4">
                          <div className="flex items-center justify-end gap-2">
                            <button
                              type="button"
                              title={
                                isSelf
                                  ? "You cannot change your own account status"
                                  : user.is_active
                                    ? "Deactivate user"
                                    : "Activate user"
                              }
                              disabled={isSelf || isBusy}
                              onClick={() => updateUserStatus(user)}
                              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 px-2.5 py-2 text-xs text-slate-300 transition hover:border-indigo-500/50 hover:bg-indigo-500/10 hover:text-indigo-200 disabled:cursor-not-allowed disabled:opacity-40"
                            >
                              {isBusy ? (
                                <Loader2 size={14} className="animate-spin" />
                              ) : user.is_active ? (
                                <UserX size={14} />
                              ) : (
                                <UserCheck size={14} />
                              )}
                              {user.is_active ? "Deactivate" : "Activate"}
                            </button>

                            <button
                              type="button"
                              title={
                                isSelf
                                  ? "You cannot delete your own account"
                                  : "Delete user"
                              }
                              disabled={isSelf || isBusy}
                              onClick={() => setConfirmUser(user)}
                              className="inline-flex items-center justify-center rounded-lg border border-red-500/20 p-2 text-red-300 transition hover:border-red-500/40 hover:bg-red-500/10 disabled:cursor-not-allowed disabled:opacity-40"
                              aria-label={`Delete ${user.full_name || "user"}`}
                            >
                              <Trash2 size={15} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          <div className="flex flex-col gap-2 border-t border-slate-800 px-5 py-4 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between">
            <span>Account data from the SciBrain administration API.</span>
            <span>{filteredUsers.length} displayed</span>
          </div>
        </section>

        {confirmUser && (
          <div
            className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
            onMouseDown={(event) => {
              if (event.target === event.currentTarget && !busyUserId) {
                setConfirmUser(null);
              }
            }}
          >
            <div
              role="dialog"
              aria-modal="true"
              aria-labelledby="delete-user-title"
              className="w-full max-w-md rounded-2xl border border-slate-700 bg-slate-900 p-6 shadow-2xl"
            >
              <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-red-500/20 bg-red-500/10 text-red-300">
                <Trash2 size={21} />
              </div>

              <h2
                id="delete-user-title"
                className="mt-5 text-lg font-semibold text-slate-100"
              >
                Delete user account?
              </h2>

              <p className="mt-2 text-sm leading-6 text-slate-400">
                You are about to permanently delete{" "}
                <span className="font-medium text-slate-200">
                  {confirmUser.full_name}
                </span>{" "}
                ({confirmUser.email}). This action cannot be undone.
              </p>

              <div className="mt-6 flex justify-end gap-3">
                <button
                  type="button"
                  disabled={Boolean(busyUserId)}
                  onClick={() => setConfirmUser(null)}
                  className="rounded-xl border border-slate-700 px-4 py-2.5 text-sm text-slate-300 hover:bg-slate-800 disabled:opacity-50"
                >
                  Cancel
                </button>

                <button
                  type="button"
                  disabled={Boolean(busyUserId)}
                  onClick={deleteUser}
                  className="inline-flex items-center gap-2 rounded-xl bg-red-500 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-red-400 disabled:opacity-50"
                >
                  {busyUserId === confirmUser.id && (
                    <Loader2 size={15} className="animate-spin" />
                  )}
                  Delete permanently
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </AdminLayout>
  );
}
