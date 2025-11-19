'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';

import { AgentVoiceButton } from '@/components/AgentVoiceButton';
import { TaskModal } from '@/components/TaskModal';
import ChoiceModal, { Choice } from '@/components/ChoiceModal';
import {
  fetchTasks,
  fetchTaskStats,
  Task,
  TaskStats,
} from '@/lib/api';

type ViewMode = 'daily' | 'weekly' | 'monthly' | 'list';
type SortField = 'scheduled_date' | 'deadline' | 'priority' | 'created_at' | 'title';
type SortOrder = 'asc' | 'desc';

const PRIORITY_ORDER = { urgent: 0, high: 1, medium: 2, low: 3 };

export default function Home() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [stats, setStats] = useState<TaskStats | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>('list');
  const [loading, setLoading] = useState(true);
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // List view filters
  const [sortField, setSortField] = useState<SortField>('scheduled_date');
  const [sortOrder, setSortOrder] = useState<SortOrder>('asc');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [priorityFilter, setPriorityFilter] = useState<string>('all');
  const [missedFilter, setMissedFilter] = useState<string>('all');
  const [startDateFilter, setStartDateFilter] = useState<string>('');
  const [endDateFilter, setEndDateFilter] = useState<string>('');
  
  // Search mode for displaying specific search results
  const [searchResultIds, setSearchResultIds] = useState<number[] | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');
  
  // Choice modal state
  const [isChoiceModalOpen, setIsChoiceModalOpen] = useState(false);
  const [choiceModalTitle, setChoiceModalTitle] = useState('');
  const [choiceModalChoices, setChoiceModalChoices] = useState<Choice[]>([]);

  const loadTasks = useCallback(async (showLoading = true) => {
    if (showLoading) {
      setLoading(true);
    }
    try {
      let startDate: Date | undefined;
      let endDate: Date | undefined;

      if (viewMode !== 'list') {
        if (viewMode === 'daily') {
          startDate = new Date(selectedDate);
          startDate.setHours(0, 0, 0, 0);
          endDate = new Date(selectedDate);
          endDate.setHours(23, 59, 59, 999);
        } else if (viewMode === 'weekly') {
          const weekStart = new Date(selectedDate);
          const day = weekStart.getDay();
          const diff = weekStart.getDate() - day;
          startDate = new Date(weekStart.setDate(diff));
          startDate.setHours(0, 0, 0, 0);
          endDate = new Date(startDate);
          endDate.setDate(startDate.getDate() + 6);
          endDate.setHours(23, 59, 59, 999);
        } else {
          startDate = new Date(
            selectedDate.getFullYear(),
            selectedDate.getMonth(),
            1,
          );
          endDate = new Date(
            selectedDate.getFullYear(),
            selectedDate.getMonth() + 1,
            0,
          );
          endDate.setHours(23, 59, 59, 999);
        }
      }

      const params: Record<string, string | number> = { limit: 500 };
      if (startDate) params.start_date = startDate.toISOString();
      if (endDate) params.end_date = endDate.toISOString();
      
      // Only apply filters if NOT in search mode
      // In search mode, we fetch all tasks and filter by searchResultIds
      if (!searchResultIds) {
        if (statusFilter !== 'all') params.status = statusFilter;
        if (priorityFilter !== 'all') params.priority = priorityFilter;
        // Apply date filters in list view (optional)
        if (viewMode === 'list') {
          if (startDateFilter) {
            const start = new Date(startDateFilter);
            start.setHours(0, 0, 0, 0);
            params.start_date = start.toISOString();
          }
          if (endDateFilter) {
            const end = new Date(endDateFilter);
            end.setHours(23, 59, 59, 999);
            params.end_date = end.toISOString();
          }
        }
      }

      const [tasksRes, statsRes] = await Promise.all([
        fetchTasks(params),
        fetchTaskStats(),
      ]);

      const sortedTasks = [...tasksRes.tasks];
      
      // Sort tasks for list view
      if (viewMode === 'list') {
        sortedTasks.sort((a, b) => {
          let aVal: string | number;
          let bVal: string | number;
          
          if (sortField === 'priority') {
            aVal = PRIORITY_ORDER[a.priority as keyof typeof PRIORITY_ORDER];
            bVal = PRIORITY_ORDER[b.priority as keyof typeof PRIORITY_ORDER];
          } else if (sortField === 'scheduled_date') {
            aVal = new Date(a.scheduled_date).getTime();
            bVal = new Date(b.scheduled_date).getTime();
          } else if (sortField === 'deadline') {
            aVal = a.deadline ? new Date(a.deadline).getTime() : Infinity;
            bVal = b.deadline ? new Date(b.deadline).getTime() : Infinity;
          } else if (sortField === 'created_at') {
            aVal = new Date(a.created_at).getTime();
            bVal = new Date(b.created_at).getTime();
          } else {
            aVal = a.title.toLowerCase();
            bVal = b.title.toLowerCase();
          }

          if (sortOrder === 'asc') {
            return aVal > bVal ? 1 : -1;
          } else {
            return aVal < bVal ? 1 : -1;
          }
        });
      }

      setTasks(sortedTasks);
      setStats(statsRes);
      
      // If in search mode, update searchResultIds to remove deleted tasks
      if (searchResultIds) {
        const currentTaskIds = sortedTasks.map(t => t.id);
        const validSearchIds = searchResultIds.filter(id => currentTaskIds.includes(id));
        
        // If all search results were deleted, clear search mode
        if (validSearchIds.length === 0) {
          setSearchResultIds(null);
          setSearchQuery('');
        } else if (validSearchIds.length !== searchResultIds.length) {
          // Some tasks were deleted, update the search results
          setSearchResultIds(validSearchIds);
        }
      }
    } catch (err) {
      console.error('Failed to load tasks:', err);
    } finally {
      if (showLoading) {
        setLoading(false);
      }
    }
  }, [viewMode, selectedDate, sortField, sortOrder, statusFilter, priorityFilter, missedFilter, startDateFilter, endDateFilter, searchResultIds, searchQuery]);

  useEffect(() => {
    loadTasks();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewMode, selectedDate, sortField, sortOrder, statusFilter, priorityFilter, missedFilter, startDateFilter, endDateFilter]);

  const handleTaskClick = (task: Task) => {
    setSelectedTask(task);
    setIsModalOpen(true);
  };

  const handleTasksUpdated = useCallback(() => {
    // Simply reload tasks without showing loading state
    loadTasks(false);
  }, [loadTasks]);

  const handleUICommand = useCallback(
    (command: {
      type: string;
      view_mode?: string;
      target_date?: string;
      sort_by?: string;
      sort_order?: string;
      filter_status?: string;
      filter_priority?: string;
      filter_missed?: string;
      filter_start_date?: string;
      filter_end_date?: string;
      search_results?: number[];
      search_query?: string;
      title?: string;
      choices?: Choice[];
    }) => {
      if (command.type === 'change_view') {
        if (command.view_mode) {
          setViewMode(command.view_mode as ViewMode);
        }
        if (command.target_date) {
          setSelectedDate(new Date(command.target_date));
        }
        // Handle list view filters and sorting
        if (command.sort_by) {
          setSortField(command.sort_by as SortField);
        }
        if (command.sort_order) {
          setSortOrder(command.sort_order as 'asc' | 'desc');
        }
        if (command.filter_status) {
          setStatusFilter(command.filter_status);
        }
        if (command.filter_priority) {
          setPriorityFilter(command.filter_priority);
        }
        if (command.filter_missed) {
          setMissedFilter(command.filter_missed);
        }
        if (command.filter_start_date) {
          setStartDateFilter(command.filter_start_date);
        }
        if (command.filter_end_date) {
          setEndDateFilter(command.filter_end_date);
        }
        
        // Handle search results mode
        if (command.search_results !== undefined) {
          setSearchResultIds(command.search_results);
          setSearchQuery(command.search_query || '');
        } else if (command.view_mode && command.view_mode !== 'list') {
          // Only clear search mode when explicitly switching away from list view
          setSearchResultIds(null);
          setSearchQuery('');
        }
        // If no search_results and staying in list view, preserve current search state
      } else if (command.type === 'show_choices') {
        // Open choice modal
        if (command.title && command.choices) {
          setChoiceModalTitle(command.title);
          setChoiceModalChoices(command.choices);
          setIsChoiceModalOpen(true);
        }
      }
    },
    []
  );
  
  // Auto-close choice modal when agent starts processing the next query
  const handleProcessingStart = useCallback(() => {
    if (isChoiceModalOpen) {
      setIsChoiceModalOpen(false);
    }
  }, [isChoiceModalOpen]);

  const goToPrevious = () => {
    const newDate = new Date(selectedDate);
    if (viewMode === 'daily') {
      newDate.setDate(newDate.getDate() - 1);
    } else if (viewMode === 'weekly') {
      newDate.setDate(newDate.getDate() - 7);
    } else if (viewMode === 'monthly') {
      newDate.setMonth(newDate.getMonth() - 1);
    }
    setSelectedDate(newDate);
  };

  const goToNext = () => {
    const newDate = new Date(selectedDate);
    if (viewMode === 'daily') {
      newDate.setDate(newDate.getDate() + 1);
    } else if (viewMode === 'weekly') {
      newDate.setDate(newDate.getDate() + 7);
    } else if (viewMode === 'monthly') {
      newDate.setMonth(newDate.getMonth() + 1);
    }
    setSelectedDate(newDate);
  };

  const goToToday = () => {
    setSelectedDate(new Date());
  };

  const getDisplayTitle = () => {
    if (viewMode === 'daily') {
      return selectedDate.toLocaleDateString('en-US', {
        weekday: 'long',
        month: 'long',
        day: 'numeric',
        year: 'numeric',
      });
    } else if (viewMode === 'weekly') {
      const weekStart = new Date(selectedDate);
      const day = weekStart.getDay();
      const diff = weekStart.getDate() - day;
      const start = new Date(weekStart.setDate(diff));
      const end = new Date(start);
      end.setDate(start.getDate() + 6);
      return `${start.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} - ${end.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}`;
    } else if (viewMode === 'monthly') {
      return selectedDate.toLocaleDateString('en-US', {
        month: 'long',
        year: 'numeric',
      });
    } else {
      return 'All Tasks';
    }
  };

  const isTaskMissed = (task: Task) => {
    // Task is missed if it has a deadline, deadline has passed, and it's not completed
    if (!task.deadline || task.status === 'completed') {
      return false;
    }
    const now = new Date();
    const deadline = new Date(task.deadline);
    return deadline < now;
  };

  const getPriorityColor = (priority: string, status?: string, isMissed?: boolean) => {
    // Red for missed tasks
    if (isMissed) {
      return 'border-red-600 bg-red-100 dark:bg-red-950/40';
    }
    
    // Grey for cancelled tasks
    if (status === 'cancelled') {
      return 'border-zinc-400 bg-zinc-100 dark:bg-zinc-800/50';
    }
    
    switch (priority) {
      case 'urgent':
        return 'border-red-500 bg-red-50 dark:bg-red-950/20';
      case 'high':
        return 'border-orange-500 bg-orange-50 dark:bg-orange-950/20';
      case 'medium':
        return 'border-blue-500 bg-blue-50 dark:bg-blue-950/20';
      case 'low':
        return 'border-green-500 bg-green-50 dark:bg-green-950/20';
      default:
        return 'border-zinc-400 bg-zinc-50 dark:bg-zinc-900';
    }
  };

  const getPriorityBadgeColor = (priority: string, status?: string) => {
    // Grey for cancelled tasks
    if (status === 'cancelled') {
      return 'bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400';
    }
    
    switch (priority) {
      case 'urgent':
        return 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300';
      case 'high':
        return 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300';
      case 'medium':
        return 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300';
      case 'low':
        return 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300';
      default:
        return 'bg-zinc-100 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-300';
    }
  };

  const getPriorityDotColor = (priority: string, status?: string) => {
    // Grey for cancelled tasks
    if (status === 'cancelled') {
      return 'bg-zinc-400';
    }
    
    switch (priority) {
      case 'urgent':
        return 'bg-red-500';
      case 'high':
        return 'bg-orange-500';
      case 'medium':
        return 'bg-blue-500';
      case 'low':
        return 'bg-green-500';
      default:
        return 'bg-zinc-400';
    }
  };

  const renderDailyView = () => {
    const hours = Array.from({ length: 24 }, (_, i) => i);
    const tasksByHour: Record<number, Task[]> = {};

    tasks.forEach((task) => {
      if (task.scheduled_date) {
        const hour = new Date(task.scheduled_date).getHours();
        if (!tasksByHour[hour]) tasksByHour[hour] = [];
        tasksByHour[hour].push(task);
      }
    });

    return (
      <div className="flex-1 overflow-auto">
        {hours.map((hour) => (
          <div key={hour} className="flex border-b border-zinc-200 dark:border-zinc-800">
            <div className="w-20 flex-shrink-0 p-4 text-sm text-zinc-500 dark:text-zinc-400">
              {hour === 0 ? '12 AM' : hour < 12 ? `${hour} AM` : hour === 12 ? '12 PM' : `${hour - 12} PM`}
            </div>
            <div className="flex-1 min-h-[80px] p-2 space-y-1">
              {tasksByHour[hour]?.map((task) => {
                const missed = isTaskMissed(task);
                return (
                  <button
                    key={task.id}
                    onClick={() => handleTaskClick(task)}
                    className={`w-full text-left p-2 rounded-lg border-l-4 transition ${getPriorityColor(task.priority, task.status, missed)}`}
                  >
                    <div className="flex items-start gap-2">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1">
                          <p className={`text-sm font-medium truncate ${task.status === 'completed' ? 'line-through text-zinc-400' : 'text-zinc-900 dark:text-zinc-100'}`}>
                            {task.title}
                          </p>
                          {missed && (
                            <span className="text-xs font-semibold text-red-600 dark:text-red-400">MISSED</span>
                          )}
                        </div>
                        <p className="text-xs text-zinc-500 dark:text-zinc-400">
                          {new Date(task.scheduled_date).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}
                          {task.deadline && (
                            <span className="ml-2 text-red-600 dark:text-red-400">
                              ⚠ Due: {new Date(task.deadline).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                            </span>
                          )}
                        </p>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    );
  };

  const renderWeeklyView = () => {
    const weekStart = new Date(selectedDate);
    const day = weekStart.getDay();
    const diff = weekStart.getDate() - day;
    const start = new Date(weekStart.setDate(diff));
    
    const days = Array.from({ length: 7 }, (_, i) => {
      const date = new Date(start);
      date.setDate(start.getDate() + i);
      return date;
    });

    const tasksByDay: Record<string, Task[]> = {};
    tasks.forEach((task) => {
      if (task.scheduled_date) {
        const dateKey = new Date(task.scheduled_date).toDateString();
        if (!tasksByDay[dateKey]) tasksByDay[dateKey] = [];
        tasksByDay[dateKey].push(task);
      }
    });

    return (
      <div className="grid grid-cols-7 gap-px bg-zinc-200 dark:bg-zinc-800 flex-1 overflow-auto">
        {days.map((date) => {
          const isToday = date.toDateString() === new Date().toDateString();
          const dayTasks = tasksByDay[date.toDateString()] || [];
          
          return (
            <div key={date.toISOString()} className="bg-white dark:bg-zinc-900 p-2 min-h-[200px]">
              <div className={`text-center mb-2 ${isToday ? 'text-emerald-600 dark:text-emerald-400 font-bold' : 'text-zinc-600 dark:text-zinc-400'}`}>
                <div className="text-xs">{date.toLocaleDateString('en-US', { weekday: 'short' })}</div>
                <div className={`text-lg ${isToday ? 'bg-emerald-600 text-white dark:bg-emerald-500 rounded-full w-8 h-8 flex items-center justify-center mx-auto' : ''}`}>
                  {date.getDate()}
                </div>
              </div>
              <div className="space-y-1">
                {dayTasks.slice(0, 5).map((task) => {
                  const missed = isTaskMissed(task);
                  return (
                    <button
                      key={task.id}
                      onClick={() => handleTaskClick(task)}
                      className={`w-full text-left p-1.5 rounded text-xs border-l-4 transition hover:bg-zinc-50 dark:hover:bg-zinc-800 ${getPriorityColor(task.priority, task.status, missed)}`}
                    >
                      <p className={`truncate ${task.status === 'completed' ? 'line-through text-zinc-400' : 'text-zinc-900 dark:text-zinc-100'}`}>
                        {task.title}
                        {missed && <span className="ml-1 text-red-600">⚠</span>}
                      </p>
                    </button>
                  );
                })}
                {dayTasks.length > 5 && (
                  <p className="text-xs text-zinc-500 dark:text-zinc-400 text-center">
                    +{dayTasks.length - 5} more
                  </p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  const renderMonthlyView = () => {
    const year = selectedDate.getFullYear();
    const month = selectedDate.getMonth();
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const daysInMonth = lastDay.getDate();
    const startingDayOfWeek = firstDay.getDay();

    const days = [];
    for (let i = 0; i < startingDayOfWeek; i++) {
      days.push(null);
    }
    for (let i = 1; i <= daysInMonth; i++) {
      days.push(new Date(year, month, i));
    }

    const tasksByDay: Record<string, Task[]> = {};
    tasks.forEach((task) => {
      if (task.scheduled_date) {
        const dateKey = new Date(task.scheduled_date).toDateString();
        if (!tasksByDay[dateKey]) tasksByDay[dateKey] = [];
        tasksByDay[dateKey].push(task);
      }
    });

    return (
      <div className="flex-1 flex flex-col">
        <div className="grid grid-cols-7 gap-px bg-zinc-200 dark:bg-zinc-800 border-b">
          {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((day) => (
            <div key={day} className="bg-white dark:bg-zinc-900 p-2 text-center text-sm font-medium text-zinc-600 dark:text-zinc-400">
              {day}
            </div>
          ))}
        </div>
        <div className="grid grid-cols-7 gap-px bg-zinc-200 dark:bg-zinc-800 flex-1 overflow-auto">
          {days.map((date, idx) => {
            if (!date) {
              return <div key={`empty-${idx}`} className="bg-white dark:bg-zinc-900 p-2 min-h-[100px]" />;
            }
            
            const isToday = date.toDateString() === new Date().toDateString();
            const dayTasks = tasksByDay[date.toDateString()] || [];
            
            return (
              <div key={date.toISOString()} className="bg-white dark:bg-zinc-900 p-2 min-h-[100px]">
                <div className={`text-sm mb-1 ${isToday ? 'bg-emerald-600 text-white dark:bg-emerald-500 rounded-full w-6 h-6 flex items-center justify-center font-bold' : 'text-zinc-600 dark:text-zinc-400'}`}>
                  {date.getDate()}
                </div>
                <div className="space-y-0.5">
                  {dayTasks.slice(0, 3).map((task) => {
                    const missed = isTaskMissed(task);
                    return (
                      <button
                        key={task.id}
                        onClick={() => handleTaskClick(task)}
                        className={`w-full text-left px-1 py-0.5 rounded text-xs truncate transition ${missed ? 'bg-red-600' : getPriorityDotColor(task.priority, task.status)} text-white hover:opacity-80 ${task.status === 'completed' ? 'line-through opacity-60' : ''}`}
                      >
                        {task.title} {missed && '⚠'}
                      </button>
                    );
                  })}
                  {dayTasks.length > 3 && (
                    <p className="text-xs text-zinc-500 dark:text-zinc-400">
                      +{dayTasks.length - 3}
                    </p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  const renderListView = () => {
    // Filter tasks if in search mode
    let displayTasks = searchResultIds 
      ? tasks.filter(task => searchResultIds.includes(task.id))
      : tasks;
    
    // Apply missed filter (client-side, since API doesn't support it)
    if (missedFilter !== 'all' && !searchResultIds) {
      displayTasks = displayTasks.filter(task => {
        const missed = isTaskMissed(task);
        return missedFilter === 'missed' ? missed : !missed;
      });
    }
    
    return (
      <div className="flex-1 overflow-auto p-6">
        {/* Show search info banner if in search mode */}
        {searchResultIds && (
          <div className="mb-4 rounded-lg bg-blue-50 dark:bg-blue-900/20 px-4 py-3 flex items-center justify-between">
            <div className="text-sm text-blue-900 dark:text-blue-100">
              <span className="font-medium">Search results for &ldquo;{searchQuery}&rdquo;</span>
              <span className="ml-2 text-blue-700 dark:text-blue-300">
                ({displayTasks.length} {displayTasks.length === 1 ? 'task' : 'tasks'} found)
              </span>
            </div>
            <button
              onClick={() => {
                setSearchResultIds(null);
                setSearchQuery('');
              }}
              className="text-sm text-blue-700 dark:text-blue-300 hover:underline"
            >
              Clear search
            </button>
          </div>
        )}
        
        <div className="mb-4 flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
              Sort by:
            </label>
            <select
              value={sortField}
              onChange={(e) => setSortField(e.target.value as SortField)}
              className="rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
            >
              <option value="scheduled_date">Scheduled Date</option>
              <option value="deadline">Deadline</option>
              <option value="priority">Priority</option>
              <option value="created_at">Created Date</option>
              <option value="title">Title</option>
            </select>
            <button
              onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
              className="rounded-lg border border-zinc-300 p-1.5 transition hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-800"
            >
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                {sortOrder === 'asc' ? (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                ) : (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                )}
              </svg>
            </button>
          </div>

          <div className="flex items-center gap-2">
            <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
              Status:
            </label>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
            >
              <option value="all">All</option>
              <option value="todo">Todo</option>
              <option value="in_progress">In Progress</option>
              <option value="completed">Completed</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </div>

          <div className="flex items-center gap-2">
            <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
              Priority:
            </label>
            <select
              value={priorityFilter}
              onChange={(e) => setPriorityFilter(e.target.value)}
              className="rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
            >
              <option value="all">All</option>
              <option value="urgent">Urgent</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </div>

          <div className="flex items-center gap-2">
            <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
              Missed:
            </label>
            <select
              value={missedFilter}
              onChange={(e) => setMissedFilter(e.target.value)}
              className="rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
            >
              <option value="all">All</option>
              <option value="missed">Missed</option>
              <option value="not_missed">Not Missed</option>
            </select>
          </div>

          <div className="flex items-center gap-2">
            <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
              Start Date:
            </label>
            <input
              type="date"
              value={startDateFilter}
              onChange={(e) => setStartDateFilter(e.target.value)}
              className="rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
            />
            {startDateFilter && (
              <button
                onClick={() => setStartDateFilter('')}
                className="text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200"
                title="Clear start date filter"
              >
                ×
              </button>
            )}
          </div>

          <div className="flex items-center gap-2">
            <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
              End Date:
            </label>
            <input
              type="date"
              value={endDateFilter}
              onChange={(e) => setEndDateFilter(e.target.value)}
              className="rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
            />
            {endDateFilter && (
              <button
                onClick={() => setEndDateFilter('')}
                className="text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200"
                title="Clear end date filter"
              >
                ×
              </button>
            )}
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="border-b border-zinc-200 dark:border-zinc-800">
              <tr className="text-left text-sm font-medium text-zinc-600 dark:text-zinc-400">
                <th className="pb-3 pr-4">Priority</th>
                <th className="pb-3 pr-4">Title</th>
                <th className="pb-3 pr-4">Status</th>
                <th className="pb-3 pr-4">Scheduled</th>
                <th className="pb-3 pr-4">Deadline</th>
                <th className="pb-3">Created</th>
              </tr>
            </thead>
            <tbody>
              {displayTasks.map((task) => {
                const missed = isTaskMissed(task);
                return (
                  <tr
                    key={task.id}
                    onClick={() => handleTaskClick(task)}
                    className={`cursor-pointer border-b border-zinc-100 transition hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-900 ${missed ? 'bg-red-50 dark:bg-red-950/20' : ''}`}
                  >
                    <td className="py-3 pr-4">
                      <span className={`rounded-full px-2 py-1 text-xs font-medium ${missed ? 'bg-red-600 text-white' : getPriorityBadgeColor(task.priority, task.status)}`}>
                        {task.priority}
                      </span>
                    </td>
                    <td className="py-3 pr-4">
                      <div className="flex items-center gap-2">
                        {task.status === 'completed' && (
                          <svg className="w-4 h-4 text-emerald-500 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                          </svg>
                        )}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <p className={`font-medium ${task.status === 'completed' ? 'line-through text-zinc-400' : 'text-zinc-900 dark:text-zinc-100'}`}>
                              {task.title}
                            </p>
                            {missed && (
                              <span className="text-xs font-semibold text-red-600 dark:text-red-400">MISSED</span>
                            )}
                          </div>
                          {task.description && (
                            <p className="text-sm text-zinc-500 dark:text-zinc-400 truncate max-w-md">
                              {task.description}
                            </p>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="py-3 pr-4">
                      <span className="text-sm text-zinc-600 dark:text-zinc-400">
                        {task.status.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="py-3 pr-4">
                      <div className="text-sm">
                        <div className="text-zinc-900 dark:text-zinc-100">
                          {new Date(task.scheduled_date).toLocaleDateString('en-US', {
                            month: 'short',
                            day: 'numeric',
                            year: 'numeric',
                          })}
                        </div>
                        <div className="text-zinc-500 dark:text-zinc-400">
                          {new Date(task.scheduled_date).toLocaleTimeString('en-US', {
                            hour: 'numeric',
                            minute: '2-digit',
                          })}
                        </div>
                      </div>
                    </td>
                    <td className="py-3 pr-4">
                      {task.deadline ? (
                        <div className="text-sm">
                          <div className={missed ? 'text-red-600 dark:text-red-400 font-semibold' : 'text-zinc-900 dark:text-zinc-100'}>
                            {new Date(task.deadline).toLocaleDateString('en-US', {
                              month: 'short',
                              day: 'numeric',
                              year: 'numeric',
                            })}
                          </div>
                          <div className={missed ? 'text-red-600 dark:text-red-400' : 'text-zinc-500 dark:text-zinc-400'}>
                            {new Date(task.deadline).toLocaleTimeString('en-US', {
                              hour: 'numeric',
                              minute: '2-digit',
                            })}
                          </div>
                        </div>
                      ) : (
                        <span className="text-sm text-zinc-400">—</span>
                      )}
                    </td>
                    <td className="py-3">
                      <span className="text-sm text-zinc-500 dark:text-zinc-400">
                        {new Date(task.created_at).toLocaleDateString('en-US', {
                          month: 'short',
                          day: 'numeric',
                        })}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  return (
    <div className="flex h-screen flex-col bg-white dark:bg-black">
      {/* Header */}
      <header className="flex items-center justify-between border-b border-zinc-200 px-6 py-4 dark:border-zinc-800">
        <div className="flex items-center gap-4">
          <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50">
            Shram AI
          </h1>
          {stats && (
            <div className="flex gap-2 text-sm">
              <span className="rounded-full bg-zinc-100 px-3 py-1 dark:bg-zinc-800">
                {stats.todo} todo
              </span>
              <span className="rounded-full bg-blue-100 px-3 py-1 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300">
                {stats.in_progress} active
              </span>
              <span className="rounded-full bg-emerald-100 px-3 py-1 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300">
                {stats.completed} done
              </span>
            </div>
          )}
        </div>

        <div className="flex items-center gap-3">
          <Link
            href="/settings"
            className="rounded-lg border border-zinc-200 p-2 text-zinc-600 hover:bg-zinc-100 dark:border-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-800"
            title="Settings"
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </Link>
          
          <div className="flex gap-1 rounded-lg border border-zinc-200 p-1 dark:border-zinc-800">
            <button
              type="button"
              onClick={() => setViewMode('list')}
              className={`rounded px-3 py-1.5 text-sm font-medium transition ${
                viewMode === 'list'
                  ? 'bg-zinc-900 text-white dark:bg-zinc-100 dark:text-black'
                  : 'text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-800'
              }`}
            >
              List
            </button>
            <button
              type="button"
              onClick={() => setViewMode('daily')}
              className={`rounded px-3 py-1.5 text-sm font-medium transition ${
                viewMode === 'daily'
                  ? 'bg-zinc-900 text-white dark:bg-zinc-100 dark:text-black'
                  : 'text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-800'
              }`}
            >
              Day
            </button>
            <button
              type="button"
              onClick={() => setViewMode('weekly')}
              className={`rounded px-3 py-1.5 text-sm font-medium transition ${
                viewMode === 'weekly'
                  ? 'bg-zinc-900 text-white dark:bg-zinc-100 dark:text-black'
                  : 'text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-800'
              }`}
            >
              Week
            </button>
            <button
              type="button"
              onClick={() => setViewMode('monthly')}
              className={`rounded px-3 py-1.5 text-sm font-medium transition ${
                viewMode === 'monthly'
                  ? 'bg-zinc-900 text-white dark:bg-zinc-100 dark:text-black'
                  : 'text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-800'
              }`}
            >
              Month
            </button>
          </div>
        </div>
      </header>

      {/* Navigation (only for calendar views) */}
      {viewMode !== 'list' && (
        <div className="flex items-center justify-between border-b border-zinc-200 px-6 py-3 dark:border-zinc-800">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={goToToday}
              className="rounded-lg border border-zinc-200 px-4 py-2 text-sm font-medium text-zinc-700 transition hover:bg-zinc-100 dark:border-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-800"
            >
              Today
            </button>
            <button
              type="button"
              onClick={goToPrevious}
              className="rounded-lg p-2 text-zinc-700 transition hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
            >
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </button>
            <button
              type="button"
              onClick={goToNext}
              className="rounded-lg p-2 text-zinc-700 transition hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
            >
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </button>
          </div>

          <h2 className="text-lg font-medium text-zinc-900 dark:text-zinc-50">
            {getDisplayTitle()}
          </h2>

          <div className="w-32" />
        </div>
      )}

      {/* Views */}
      {loading ? (
        <div className="flex flex-1 items-center justify-center">
          <p className="text-zinc-500 dark:text-zinc-400">Loading...</p>
        </div>
      ) : (
        <>
          {viewMode === 'daily' && renderDailyView()}
          {viewMode === 'weekly' && renderWeeklyView()}
          {viewMode === 'monthly' && renderMonthlyView()}
          {viewMode === 'list' && renderListView()}
        </>
      )}

      {/* Task Modal */}
      {selectedTask && (
        <TaskModal
          task={selectedTask}
          isOpen={isModalOpen}
          onClose={() => {
            setIsModalOpen(false);
            setSelectedTask(null);
          }}
          onUpdate={handleTasksUpdated}
        />
      )}

      {/* Choice Modal */}
      <ChoiceModal
        isOpen={isChoiceModalOpen}
        title={choiceModalTitle}
        choices={choiceModalChoices}
        onClose={() => setIsChoiceModalOpen(false)}
      />

      {/* Agent Voice Button */}
      <AgentVoiceButton 
        onTasksUpdated={handleTasksUpdated} 
        onUICommand={handleUICommand}
        onProcessingStart={handleProcessingStart}
      />
    </div>
  );
}
