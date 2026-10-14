import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Keyboard } from "@phosphor-icons/react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useHotkeys, SHORTCUTS } from "@/lib/hotkeys";

export default function Shortcuts() {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  useHotkeys({
    "?": () => setOpen((o) => !o),
    "g d": () => navigate("/app"),
    "g k": () => navigate("/app/keys"),
    "g h": () => navigate("/how-it-works"),
    "g a": () => navigate("/admin"),
  });
  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-4 right-4 z-40 bg-white border-2 border-[#0A0A0A] shadow-[3px_3px_0_#0A0A0A] px-3 py-2 text-xs font-bold uppercase tracking-wider inline-flex items-center gap-2 hover:bg-[#F3F4F6] transition-colors"
        data-testid="shortcuts-button"
        title="Keyboard shortcuts (?)"
      >
        <Keyboard size={16} weight="bold" /> ?
      </button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="border-2 border-[#0A0A0A] rounded-sm max-w-lg" data-testid="shortcuts-dialog">
          <DialogHeader>
            <DialogTitle className="font-head font-black text-2xl tracking-tight">Keyboard shortcuts</DialogTitle>
          </DialogHeader>
          <div className="space-y-5 max-h-[60vh] overflow-auto">
            {SHORTCUTS.map(([group, items]) => (
              <div key={group}>
                <div className="overline mb-2">{group}</div>
                <ul className="space-y-1.5">
                  {items.map(([k, d]) => (
                    <li key={k} className="flex justify-between text-sm gap-4">
                      <span className="text-[#4B5563]">{d}</span>
                      <kbd className="border-2 border-[#0A0A0A] px-1.5 text-xs font-bold whitespace-nowrap">{k}</kbd>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
