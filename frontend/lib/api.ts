// API client for backend tasks

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000/api';

export type TaskPriority = 'low' | 'medium' | 'high' | 'urgent';
export type TaskStatus = 'todo' | 'in_progress' | 'completed' | 'cancelled';

export type Task = {
  id: number;
  title: string;
  description?: string;
  notes?: string;
  priority: TaskPriority;
  status: TaskStatus;
  created_at: string;
  updated_at: string;
  scheduled_date: string; // When task is planned to be done (REQUIRED)
  deadline?: string; // When task MUST be completed by (OPTIONAL)
  completed_at?: string;
};

export type TaskListResponse = {
  tasks: Task[];
  total: number;
  skip: number;
  limit: number;
};

export type TaskStats = {
  total: number;
  completed: number;
  in_progress: number;
  todo: number;
  upcoming_deadlines: number;
};

export async function fetchTasks(params?: {
  skip?: number;
  limit?: number;
  status?: TaskStatus;
  priority?: TaskPriority;
  search?: string;
  start_date?: string;
  end_date?: string;
}): Promise<TaskListResponse> {
  const searchParams = new URLSearchParams();
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        searchParams.append(key, String(value));
      }
    });
  }

  const url = `${API_BASE}/tasks?${searchParams.toString()}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to fetch tasks: ${res.statusText}`);
  return res.json();
}

export async function fetchTaskStats(): Promise<TaskStats> {
  const res = await fetch(`${API_BASE}/tasks/stats/summary`);
  if (!res.ok) throw new Error(`Failed to fetch stats: ${res.statusText}`);
  return res.json();
}

export async function createTask(task: {
  title: string;
  description?: string;
  notes?: string;
  priority?: TaskPriority;
  status?: TaskStatus;
  scheduled_date: string; // REQUIRED
  deadline?: string; // OPTIONAL
}): Promise<Task> {
  const res = await fetch(`${API_BASE}/tasks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(task),
  });
  if (!res.ok) throw new Error(`Failed to create task: ${res.statusText}`);
  return res.json();
}

export async function updateTask(
  id: number,
  updates: Partial<Omit<Task, 'id' | 'created_at' | 'updated_at'>>,
): Promise<Task> {
  const res = await fetch(`${API_BASE}/tasks/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
  });
  if (!res.ok) throw new Error(`Failed to update task: ${res.statusText}`);
  return res.json();
}

export async function deleteTask(id: number): Promise<void> {
  const res = await fetch(`${API_BASE}/tasks/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error(`Failed to delete task: ${res.statusText}`);
}

