import { Link } from "react-router-dom";
import { Lightning } from "@phosphor-icons/react";
import { useAuth } from "@/context/AuthContext";

export default function PublicHeader() {
  const { user } = useAuth();
  return (
    <header className="border-b-2 border-[#0A0A0A] bg-white sticky top-0 z-30">
      <div className="max-w-[1300px] mx-auto px-6 h-16 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2" data-testid="public-brand">
          <Lightning size={26} weight="fill" className="text-[#002FA7]" />
          <span className="font-head font-black text-xl tracking-tighter">TOKENFORGE</span>
        </Link>
        <nav className="flex items-center gap-3">
          <Link to="/how-it-works" className="hidden sm:inline-flex text-xs font-bold uppercase tracking-wider px-3 py-2 hover:text-[#002FA7]" data-testid="header-how-it-works">
            How it works
          </Link>
          {user ? (
            <Link to="/app" className="btn-brutal py-2 px-4 text-xs" data-testid="header-dashboard">
              Dashboard
            </Link>
          ) : (
            <>
              <Link to="/login" className="btn-ghost py-2 px-4 text-xs" data-testid="header-login">
                Log in
              </Link>
              <Link to="/register" className="btn-brutal py-2 px-4 text-xs" data-testid="header-signup">
                Start free
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}
