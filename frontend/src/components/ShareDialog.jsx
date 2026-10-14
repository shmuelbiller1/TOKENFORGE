import { useState } from "react";
import { toast } from "sonner";
import { Copy, Globe, Lock } from "@phosphor-icons/react";
import api, { formatApiErrorDetail } from "@/lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";

export default function ShareDialog({ open, onOpenChange, job, onChange }) {
  const [busy, setBusy] = useState(false);
  const url = job.share_token ? `${window.location.origin}/r/${job.share_token}` : "";

  const toggle = async (enabled) => {
    setBusy(true);
    try {
      const { data } = await api.post(`/jobs/${job.id}/share`, { enabled });
      onChange({ share_enabled: data.enabled, share_token: data.token });
      toast.success(enabled ? "Public link is live" : "Link turned off. The report is private again");
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail) || e.message);
    } finally {
      setBusy(false);
    }
  };

  const copy = async () => {
    await navigator.clipboard.writeText(url);
    toast.success("Link copied");
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="border-2 border-[#0A0A0A] rounded-sm max-w-lg" data-testid="share-dialog">
        <DialogHeader>
          <DialogTitle className="font-head font-black text-2xl tracking-tight">Share token report</DialogTitle>
          <DialogDescription className="text-sm text-[#4B5563]">
            Anyone with the link sees the stats and a preview of the optimized output (first 6,000 characters).
            Your original files, preserved variants and the reconstruction map are never shown.
          </DialogDescription>
        </DialogHeader>
        {job.share_enabled ? (
          <div className="space-y-4">
            <div className="flex">
              <input readOnly value={url} className="input-brutal flex-1 text-xs rounded-r-none border-r-0" data-testid="share-url" onFocus={(e) => e.target.select()} />
              <button onClick={copy} className="btn-brutal rounded-l-none" data-testid="share-copy">
                <Copy size={16} weight="bold" /> Copy
              </button>
            </div>
            <div className="flex justify-between items-center">
              <span className="inline-flex items-center gap-1 text-xs font-bold uppercase text-[#34C759]"><Globe size={14} weight="bold" /> Public</span>
              <button onClick={() => toggle(false)} disabled={busy} className="btn-ghost text-xs" data-testid="share-disable">
                <Lock size={16} weight="bold" /> Turn link off
              </button>
            </div>
          </div>
        ) : (
          <div className="flex justify-between items-center">
            <span className="inline-flex items-center gap-1 text-xs font-bold uppercase text-[#4B5563]"><Lock size={14} weight="bold" /> Private</span>
            <button onClick={() => toggle(true)} disabled={busy || job.status !== "completed"} className="btn-brutal" data-testid="share-enable">
              <Globe size={16} weight="bold" /> Create public link
            </button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
