'use client';

export interface Choice {
  id: string;
  label: string;
  description: string;
  value: string;
}

interface ChoiceModalProps {
  isOpen: boolean;
  title: string;
  choices: Choice[];
  onClose?: () => void;
}

export default function ChoiceModal({
  isOpen,
  title,
  choices,
  onClose,
}: ChoiceModalProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed bottom-32 left-1/2 z-50 flex -translate-x-1/2 flex-col items-center">
      <div className="relative w-full max-w-lg rounded-2xl bg-white shadow-2xl dark:bg-zinc-900 flex flex-col border border-zinc-200 dark:border-zinc-800 max-h-[60vh] overflow-hidden mb-2">
        {/* Arrow pointing down to button */}
        <div className="absolute -bottom-2 left-1/2 -translate-x-1/2">
          <div className="h-4 w-4 rotate-45 border-r border-b border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900"></div>
        </div>
        {/* Header */}
        <div className="border-b border-zinc-200 px-6 py-5 dark:border-zinc-800">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-100 dark:bg-emerald-900/30">
                <svg className="h-5 w-5 text-emerald-600 dark:text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
                {title}
              </h2>
            </div>
            
            {/* Close Button */}
            {onClose && (
              <button
                onClick={onClose}
                className="rounded-lg p-2 text-zinc-500 transition hover:bg-zinc-100 hover:text-zinc-700 dark:hover:bg-zinc-800 dark:hover:text-zinc-300"
                aria-label="Close modal"
              >
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>
        </div>

        {/* Choices - Read-only Display */}
        <div className="flex-1 overflow-y-auto px-6 py-5">
          <div className="space-y-2">
            {choices.map((choice) => (
              <div
                key={choice.id}
                className="flex items-start gap-4 rounded-lg border border-zinc-200 bg-zinc-50 px-4 py-3 dark:border-zinc-800 dark:bg-zinc-900/50"
              >
                {/* Choice Label Badge */}
                <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-emerald-600 font-bold text-white text-sm shadow-sm">
                  {choice.label}
                </div>
                
                {/* Choice Description */}
                <div className="flex-1 min-w-0 pt-0.5">
                  <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100 leading-relaxed">
                    {choice.description}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Footer - Instructions */}
        <div className="border-t border-zinc-200 bg-zinc-50 px-6 py-3 dark:border-zinc-800 dark:bg-zinc-900/50">
          <div className="flex items-center gap-2 text-xs text-zinc-600 dark:text-zinc-400">
            <svg className="h-3.5 w-3.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
            </svg>
            <p>Say the letter or number to select</p>
          </div>
        </div>
      </div>
    </div>
  );
}

