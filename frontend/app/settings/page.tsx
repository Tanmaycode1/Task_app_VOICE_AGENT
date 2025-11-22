'use client';

import { useEffect, useState, useRef } from 'react';
import Link from 'next/link';

// API base URL from environment variable
const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000/api';

type ConversationMessage = {
  id: number;
  role: string;
  content: string;
  tool_calls: string | null;
  tool_results: string | null;
  created_at: string;
};

type PaginationInfo = {
  total: number;
  page: number;
  limit: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
};

type ApiCost = {
  id: number;
  user_query: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  input_cost: number;
  output_cost: number;
  total_cost: number;
  iterations: number;
  tool_calls_count: number;
  created_at: string;
};

type CostSummary = {
  total_cost: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_requests: number;
  average_cost_per_request: number;
};

export default function SettingsPage() {
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [pagination, setPagination] = useState<PaginationInfo | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  
  // Cost tracking state
  const [costs, setCosts] = useState<ApiCost[]>([]);
  const [costLoading, setCostLoading] = useState(true);
  const [costPage, setCostPage] = useState(1);
  const [costPagination, setCostPagination] = useState<PaginationInfo | null>(null);
  const [costSummary, setCostSummary] = useState<CostSummary | null>(null);
  const [activeTab, setActiveTab] = useState<'conversation' | 'costs'>('conversation');

  const loadHistory = async (pageNum: number = page) => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.append('page', pageNum.toString());
      params.append('limit', '50');

      const response = await fetch(`${API_BASE}/conversation/history?${params}`);
      const data = await response.json();
      
      if (data.success) {
        // Messages are already sorted chronologically (oldest first) from backend
        const sorted = [...data.messages].sort((a, b) => 
          new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
        );
        setMessages(sorted);
        setPagination({
          total: data.total,
          page: data.page,
          limit: data.limit,
          total_pages: data.total_pages,
          has_next: data.has_next,
          has_previous: data.has_previous,
        });
      }
    } catch (error) {
      console.error('Failed to load history:', error);
    } finally {
      setLoading(false);
    }
  };

  const handlePageChange = (newPage: number) => {
    if (newPage >= 1 && pagination && newPage <= pagination.total_pages) {
      setPage(newPage);
      loadHistory(newPage);
      // Scroll to top when page changes
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  const clearHistory = async () => {
    if (!confirm('Are you sure you want to clear all conversation history?')) {
      return;
    }

    try {
      const response = await fetch(`${API_BASE}/conversation/history`, {
        method: 'DELETE',
      });
      const data = await response.json();
      
      if (data.success) {
        alert(data.message);
        loadHistory();
      }
    } catch (error) {
      console.error('Failed to clear history:', error);
      alert('Failed to clear history');
    }
  };

  const loadCostHistory = async (pageNum: number = costPage) => {
    setCostLoading(true);
    try {
      const params = new URLSearchParams();
      params.append('page', pageNum.toString());
      params.append('limit', '50');

      const response = await fetch(`${API_BASE}/costs/history?${params}`);
      const data = await response.json();
      
      if (data.success) {
        setCosts(data.costs);
        setCostSummary(data.summary);
        setCostPagination({
          total: data.total,
          page: data.page,
          limit: data.limit,
          total_pages: data.total_pages,
          has_next: data.has_next,
          has_previous: data.has_previous,
        });
      }
    } catch (error) {
      console.error('Failed to load cost history:', error);
    } finally {
      setCostLoading(false);
    }
  };

  const handleCostPageChange = (newPage: number) => {
    if (newPage >= 1 && costPagination && newPage <= costPagination.total_pages) {
      setCostPage(newPage);
      loadCostHistory(newPage);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  useEffect(() => {
    loadHistory(1);
    loadCostHistory(1);
  }, []);

  // Auto-scroll to bottom (newest messages) when on last page
  useEffect(() => {
    if (!loading && messages.length > 0 && pagination && page === pagination.total_pages) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, loading, page, pagination]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const formatToolData = (jsonString: string | null) => {
    if (!jsonString) return null;
    try {
      const data = JSON.parse(jsonString);
      return JSON.stringify(data, null, 2);
    } catch {
      return jsonString;
    }
  };

  return (
    <div className="flex min-h-screen flex-col bg-gradient-to-br from-zinc-50 to-zinc-100 dark:from-zinc-950 dark:to-zinc-900">
      {/* Header */}
      <header className="border-b border-zinc-200 bg-white/80 backdrop-blur-sm dark:border-zinc-800 dark:bg-zinc-900/80">
        <div className="mx-auto max-w-7xl px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link
                href="/"
                className="flex items-center gap-2 text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
              >
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                </svg>
                Back
              </Link>
              <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
                Settings
              </h1>
            </div>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="mx-auto w-full max-w-7xl flex-1 px-6 py-8">
        {/* Tabs */}
        <div className="mb-6 flex gap-2 border-b border-zinc-200 dark:border-zinc-800">
          <button
            onClick={() => setActiveTab('conversation')}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === 'conversation'
                ? 'border-b-2 border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400'
                : 'text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100'
            }`}
          >
            Conversation History
          </button>
          <button
            onClick={() => setActiveTab('costs')}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === 'costs'
                ? 'border-b-2 border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400'
                : 'text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100'
            }`}
          >
            Cost History
          </button>
        </div>

        {activeTab === 'conversation' && (
          <>
            <div className="mb-6 flex items-center justify-between">
              <div>
                <h2 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">
                  Conversation History
                </h2>
                <p className="text-sm text-zinc-500 dark:text-zinc-400">
                  {pagination 
                    ? `Showing ${((page - 1) * pagination.limit) + 1}-${Math.min(page * pagination.limit, pagination.total)} of ${pagination.total} messages (Page ${page} of ${pagination.total_pages})`
                    : 'All conversations sorted chronologically (oldest → newest)'}
                </p>
              </div>

          <div className="flex items-center gap-3">
            <button
              onClick={scrollToBottom}
              className="rounded-lg border border-zinc-300 bg-white px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800"
            >
              Scroll to Latest
            </button>
            <button
              onClick={clearHistory}
              className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700"
            >
              Clear History
            </button>
          </div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <p className="text-zinc-500 dark:text-zinc-400">Loading...</p>
          </div>
        ) : messages.length === 0 ? (
          <div className="flex items-center justify-center py-12">
            <p className="text-zinc-500 dark:text-zinc-400">No conversation history yet</p>
          </div>
        ) : (
          <div className="space-y-4">
            {messages.map((message) => (
              <div
                key={message.id}
                className={`rounded-lg border p-4 ${
                  message.role === 'user'
                    ? 'border-blue-200 bg-blue-50 dark:border-blue-900 dark:bg-blue-950/20'
                    : 'border-green-200 bg-green-50 dark:border-green-900 dark:bg-green-950/20'
                }`}
              >
                <div className="mb-2 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span
                      className={`rounded-full px-3 py-1 text-xs font-medium ${
                        message.role === 'user'
                          ? 'bg-blue-600 text-white'
                          : 'bg-green-600 text-white'
                      }`}
                    >
                      {message.role.toUpperCase()}
                    </span>
                    <span className="text-xs text-zinc-500 dark:text-zinc-400">
                      {new Date(message.created_at).toLocaleString()}
                    </span>
                  </div>
                </div>

                {message.content && (
                  <div className="mb-2">
                    <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                      Content:
                    </p>
                    <p className="mt-1 text-sm text-zinc-900 dark:text-zinc-100">
                      {message.content}
                    </p>
                  </div>
                )}

                {message.tool_calls && (
                  <div className="mb-2">
                    <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                      Tool Calls:
                    </p>
                    <pre className="mt-1 overflow-x-auto rounded bg-zinc-800 p-2 text-xs text-zinc-100">
                      {formatToolData(message.tool_calls)}
                    </pre>
                  </div>
                )}

                {message.tool_results && (
                  <div>
                    <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                      Tool Results:
                    </p>
                    <pre className="mt-1 overflow-x-auto rounded bg-zinc-800 p-2 text-xs text-zinc-100">
                      {formatToolData(message.tool_results)}
                    </pre>
                  </div>
                )}
              </div>
            ))}
            {/* Scroll target - newest messages are at the bottom */}
            <div ref={messagesEndRef} />
          </div>
        )}

        {/* Pagination Controls */}
        {pagination && pagination.total_pages > 1 && (
          <div className="mt-8 flex items-center justify-center gap-4">
            <button
              onClick={() => handlePageChange(page - 1)}
              disabled={!pagination.has_previous || loading}
              className={`rounded-lg border px-4 py-2 text-sm font-medium transition-colors ${
                pagination.has_previous && !loading
                  ? 'border-zinc-300 bg-white text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800'
                  : 'border-zinc-200 bg-zinc-100 text-zinc-400 cursor-not-allowed dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-600'
              }`}
            >
              Previous
            </button>

            <div className="flex items-center gap-2">
              {/* Show page numbers */}
              {Array.from({ length: Math.min(5, pagination.total_pages) }, (_, i) => {
                let pageNum: number;
                if (pagination.total_pages <= 5) {
                  pageNum = i + 1;
                } else if (page <= 3) {
                  pageNum = i + 1;
                } else if (page >= pagination.total_pages - 2) {
                  pageNum = pagination.total_pages - 4 + i;
                } else {
                  pageNum = page - 2 + i;
                }

                return (
                  <button
                    key={pageNum}
                    onClick={() => handlePageChange(pageNum)}
                    disabled={loading}
                    className={`rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${
                      pageNum === page
                        ? 'border-blue-500 bg-blue-600 text-white dark:border-blue-400 dark:bg-blue-500'
                        : 'border-zinc-300 bg-white text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800'
                    } ${loading ? 'cursor-not-allowed opacity-50' : ''}`}
                  >
                    {pageNum}
                  </button>
                );
              })}
            </div>

            <button
              onClick={() => handlePageChange(page + 1)}
              disabled={!pagination.has_next || loading}
              className={`rounded-lg border px-4 py-2 text-sm font-medium transition-colors ${
                pagination.has_next && !loading
                  ? 'border-zinc-300 bg-white text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800'
                  : 'border-zinc-200 bg-zinc-100 text-zinc-400 cursor-not-allowed dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-600'
              }`}
            >
              Next
            </button>
          </div>
        )}
          </>
        )}

        {activeTab === 'costs' && (
          <>
            {/* Cost Summary */}
            {costSummary && (
              <div className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-4">
                <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
                  <p className="text-sm text-zinc-500 dark:text-zinc-400">Total Cost</p>
                  <p className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
                    ${costSummary.total_cost.toFixed(4)}
                  </p>
                </div>
                <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
                  <p className="text-sm text-zinc-500 dark:text-zinc-400">Total Requests</p>
                  <p className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
                    {costSummary.total_requests.toLocaleString()}
                  </p>
                </div>
                <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
                  <p className="text-sm text-zinc-500 dark:text-zinc-400">Avg per Request</p>
                  <p className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
                    ${costSummary.average_cost_per_request.toFixed(6)}
                  </p>
                </div>
                <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
                  <p className="text-sm text-zinc-500 dark:text-zinc-400">Total Tokens</p>
                  <p className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
                    {(costSummary.total_input_tokens + costSummary.total_output_tokens).toLocaleString()}
                  </p>
                </div>
              </div>
            )}

            <div className="mb-6 flex items-center justify-between">
              <div>
                <h2 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">
                  API Cost History
                </h2>
                <p className="text-sm text-zinc-500 dark:text-zinc-400">
                  {costPagination 
                    ? `Showing ${((costPage - 1) * costPagination.limit) + 1}-${Math.min(costPage * costPagination.limit, costPagination.total)} of ${costPagination.total} requests (Page ${costPage} of ${costPagination.total_pages})`
                    : 'All API costs sorted by most recent'}
                </p>
              </div>
            </div>

            {costLoading ? (
              <div className="flex items-center justify-center py-12">
                <p className="text-zinc-500 dark:text-zinc-400">Loading...</p>
              </div>
            ) : costs.length === 0 ? (
              <div className="flex items-center justify-center py-12">
                <p className="text-zinc-500 dark:text-zinc-400">No cost history yet</p>
              </div>
            ) : (
              <div className="space-y-4">
                {costs.map((cost) => (
                  <div
                    key={cost.id}
                    className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900"
                  >
                    <div className="mb-3 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="rounded-full bg-purple-600 px-3 py-1 text-xs font-medium text-white">
                          {cost.model}
                        </span>
                        <span className="text-xs text-zinc-500 dark:text-zinc-400">
                          {new Date(cost.created_at).toLocaleString()}
                        </span>
                      </div>
                      <div className="text-right">
                        <p className="text-lg font-bold text-zinc-900 dark:text-zinc-100">
                          ${cost.total_cost.toFixed(6)}
                        </p>
                        <p className="text-xs text-zinc-500 dark:text-zinc-400">
                          {cost.iterations} iteration{cost.iterations !== 1 ? 's' : ''} • {cost.tool_calls_count} tool{cost.tool_calls_count !== 1 ? 's' : ''}
                        </p>
                      </div>
                    </div>

                    <div className="mb-2">
                      <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                        Query:
                      </p>
                      <p className="mt-1 text-sm text-zinc-900 dark:text-zinc-100">
                        {cost.user_query || '(No query)'}
                      </p>
                    </div>

                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div>
                        <p className="text-zinc-500 dark:text-zinc-400">Input Tokens</p>
                        <p className="font-medium text-zinc-900 dark:text-zinc-100">
                          {cost.input_tokens.toLocaleString()} (${cost.input_cost.toFixed(6)})
                        </p>
                      </div>
                      <div>
                        <p className="text-zinc-500 dark:text-zinc-400">Output Tokens</p>
                        <p className="font-medium text-zinc-900 dark:text-zinc-100">
                          {cost.output_tokens.toLocaleString()} (${cost.output_cost.toFixed(6)})
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Cost Pagination */}
            {costPagination && costPagination.total_pages > 1 && (
              <div className="mt-8 flex items-center justify-center gap-4">
                <button
                  onClick={() => handleCostPageChange(costPage - 1)}
                  disabled={!costPagination.has_previous || costLoading}
                  className={`rounded-lg border px-4 py-2 text-sm font-medium transition-colors ${
                    costPagination.has_previous && !costLoading
                      ? 'border-zinc-300 bg-white text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800'
                      : 'border-zinc-200 bg-zinc-100 text-zinc-400 cursor-not-allowed dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-600'
                  }`}
                >
                  Previous
                </button>

                <div className="flex items-center gap-2">
                  {Array.from({ length: Math.min(5, costPagination.total_pages) }, (_, i) => {
                    let pageNum: number;
                    if (costPagination.total_pages <= 5) {
                      pageNum = i + 1;
                    } else if (costPage <= 3) {
                      pageNum = i + 1;
                    } else if (costPage >= costPagination.total_pages - 2) {
                      pageNum = costPagination.total_pages - 4 + i;
                    } else {
                      pageNum = costPage - 2 + i;
                    }

                    return (
                      <button
                        key={pageNum}
                        onClick={() => handleCostPageChange(pageNum)}
                        disabled={costLoading}
                        className={`rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${
                          pageNum === costPage
                            ? 'border-blue-500 bg-blue-600 text-white dark:border-blue-400 dark:bg-blue-500'
                            : 'border-zinc-300 bg-white text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800'
                        } ${costLoading ? 'cursor-not-allowed opacity-50' : ''}`}
                      >
                        {pageNum}
                      </button>
                    );
                  })}
                </div>

                <button
                  onClick={() => handleCostPageChange(costPage + 1)}
                  disabled={!costPagination.has_next || costLoading}
                  className={`rounded-lg border px-4 py-2 text-sm font-medium transition-colors ${
                    costPagination.has_next && !costLoading
                      ? 'border-zinc-300 bg-white text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800'
                      : 'border-zinc-200 bg-zinc-100 text-zinc-400 cursor-not-allowed dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-600'
                  }`}
                >
                  Next
                </button>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}

