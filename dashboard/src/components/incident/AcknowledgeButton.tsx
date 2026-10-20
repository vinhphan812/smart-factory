/**
 * AcknowledgeButton - action button for acknowledging/resolve incidents
 */

import React, { useState } from 'react';

interface AcknowledgeButtonProps {
  incidentId: string;
  currentStatus: 'open' | 'acknowledged' | 'resolved';
  disabled?: boolean;
  onAcknowledge?: (incidentId: string, notes?: string) => Promise<boolean>;
  onResolve?: (incidentId: string, notes?: string) => Promise<boolean>;
}

export function AcknowledgeButton({
  incidentId,
  currentStatus,
  disabled = false,
  onAcknowledge,
  onResolve,
}: AcknowledgeButtonProps) {
  const [loading, setLoading] = useState(false);
  const [notes, setNotes] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [modalAction, setModalAction] = useState<'acknowledge' | 'resolve'>('acknowledge');
  const [error, setError] = useState<string | null>(null);

  const handleAction = async (action: 'acknowledge' | 'resolve') => {
    setModalAction(action);
    setShowModal(true);
    setError(null);
  };

  const confirmAction = async () => {
    setLoading(true);
    setError(null);

    try {
      let success = false;
      if (modalAction === 'acknowledge' && onAcknowledge) {
        success = await onAcknowledge(incidentId, notes || undefined);
      } else if (modalAction === 'resolve' && onResolve) {
        success = await onResolve(incidentId, notes || undefined);
      }

      if (success) {
        setShowModal(false);
        setNotes('');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Action failed');
    } finally {
      setLoading(false);
    }
  };

  if (currentStatus === 'resolved') {
    return (
      <span className="inline-flex items-center gap-2 px-3 py-1.5 bg-green-900/30 border border-green-700 rounded-lg text-sm text-green-400">
        <span>✓</span>
        <span>Resolved</span>
      </span>
    );
  }

  return (
    <>
      <div className="flex items-center gap-2">
        {currentStatus === 'open' && (
          <button
            onClick={() => handleAction('acknowledge')}
            disabled={disabled || loading}
            className="inline-flex items-center gap-2 px-3 py-1.5 bg-blue-900/50 border border-blue-700 rounded-lg text-sm text-blue-300 hover:bg-blue-800/50 hover:border-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading && modalAction === 'acknowledge' ? (
              <span className="animate-spin">⏳</span>
            ) : (
              <span>✅</span>
            )}
            <span>Acknowledge</span>
          </button>
        )}

        <button
          onClick={() => handleAction('resolve')}
          disabled={disabled || loading}
          className="inline-flex items-center gap-2 px-3 py-1.5 bg-green-900/50 border border-green-700 rounded-lg text-sm text-green-300 hover:bg-green-800/50 hover:border-green-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading && modalAction === 'resolve' ? (
            <span className="animate-spin">⏳</span>
          ) : (
            <span>✓</span>
          )}
          <span>Resolve</span>
        </button>
      </div>

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70">
          <div className="bg-gray-800 border border-gray-700 rounded-xl p-6 w-full max-w-md shadow-2xl">
            <h3 className="text-lg font-semibold text-gray-100 mb-4">
              {modalAction === 'acknowledge' ? 'Acknowledge Incident' : 'Resolve Incident'}
            </h3>

            {error && (
              <div className="mb-4 p-3 bg-red-900/30 border border-red-700 rounded-lg text-sm text-red-300">
                {error}
              </div>
            )}

            <div className="mb-4">
              <label
                htmlFor="action-notes"
                className="block text-sm font-medium text-gray-300 mb-2"
              >
                Notes (optional)
              </label>
              <textarea
                id="action-notes"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Add any notes about this action..."
                className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-[var(--color-primary)] resize-none"
                rows={3}
              />
            </div>

            <div className="flex justify-end gap-3">
              <button
                onClick={() => {
                  setShowModal(false);
                  setNotes('');
                  setError(null);
                }}
                disabled={loading}
                className="px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-sm text-gray-300 hover:bg-gray-600 disabled:opacity-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={confirmAction}
                disabled={loading}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 ${
                  modalAction === 'acknowledge'
                    ? 'bg-blue-700 border border-blue-600 text-white hover:bg-blue-600'
                    : 'bg-green-700 border border-green-600 text-white hover:bg-green-600'
                }`}
              >
                {loading ? 'Processing...' : modalAction === 'acknowledge' ? 'Acknowledge' : 'Resolve'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export default AcknowledgeButton;
