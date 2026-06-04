"use client";

import { useState, useEffect } from "react";
import { Shield, Trash2, MessageSquare, AlertCircle } from "lucide-react";

export default function AdminDashboard() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [error, setError] = useState("");
  const [reviews, setReviews] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    if (username === "Suraj" && password === "1803ks1415ms") {
      setIsAuthenticated(true);
      fetchReviews();
    } else {
      setError("Invalid credentials");
    }
  };

  const fetchReviews = async () => {
    try {
      const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "https://study-synthesizer.onrender.com";
      const res = await fetch(`${API_BASE_URL}/api/admin/feedback?secret=${password}`);
      if (res.ok) {
        const data = await res.json();
        setReviews(data);
      }
    } catch (err) {
      console.error("Failed to fetch reviews", err);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Are you sure you want to delete this review?")) return;
    
    setLoading(true);
    try {
      const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${API_BASE_URL}/api/admin/feedback/${id}?secret=${password}`, {
        method: "DELETE"
      });
      if (res.ok) {
        setReviews(reviews.filter(r => r.id !== id));
      } else {
        alert("Failed to delete review");
      }
    } catch (err) {
      console.error("Delete failed", err);
    }
    setLoading(false);
  };

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center p-6 text-slate-900">
        <form onSubmit={handleLogin} className="bg-white p-10 rounded-3xl shadow-2xl max-w-sm w-full space-y-6">
          <div className="flex justify-center mb-4 text-indigo-600">
            <Shield className="w-12 h-12" />
          </div>
          <h1 className="text-2xl font-bold text-center">Admin Login</h1>
          {error && <div className="text-red-500 text-sm text-center font-medium bg-red-50 py-2 rounded-lg">{error}</div>}
          <div className="space-y-4">
            <input
              type="text"
              placeholder="Username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-4 py-3 rounded-xl border border-slate-200 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 transition-all"
            />
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-4 py-3 rounded-xl border border-slate-200 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 transition-all"
            />
          </div>
          <button type="submit" className="w-full py-3 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-xl transition-all shadow-md">
            Login
          </button>
        </form>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 p-8 font-sans">
      <div className="max-w-4xl mx-auto space-y-8">
        <header className="flex justify-between items-center bg-white p-6 rounded-3xl shadow-sm border border-slate-200">
          <div className="flex items-center space-x-3 text-indigo-600">
            <Shield className="w-8 h-8" />
            <h1 className="text-2xl font-bold text-slate-900">Moderation Dashboard</h1>
          </div>
          <div className="text-sm font-semibold text-slate-500">
            Logged in as {username}
          </div>
        </header>

        <div className="bg-white rounded-3xl shadow-sm border border-slate-200 overflow-hidden">
          {reviews.length === 0 ? (
            <div className="p-12 text-center text-slate-500 flex flex-col items-center">
              <CheckCircle className="w-12 h-12 mb-4 text-emerald-400" />
              <p className="text-lg">No reviews found. All clean!</p>
            </div>
          ) : (
            <ul className="divide-y divide-slate-100">
              {reviews.map((review) => (
                <li key={review.id} className="p-6 hover:bg-slate-50 transition-colors flex items-start justify-between">
                  <div className="flex space-x-4">
                    <div className={`p-3 rounded-full mt-1 ${review.rating === 'up' ? 'bg-emerald-100 text-emerald-600' : 'bg-red-100 text-red-600'}`}>
                      <MessageSquare className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="flex items-center space-x-2 mb-1">
                        <span className={`text-xs font-bold uppercase tracking-wider ${review.rating === 'up' ? 'text-emerald-600' : 'text-red-600'}`}>
                          {review.rating === 'up' ? 'Positive' : 'Negative'}
                        </span>
                        <span className="text-xs text-slate-400">•</span>
                        <span className="text-xs text-slate-400">{new Date(review.timestamp).toLocaleString()}</span>
                      </div>
                      <p className="text-slate-900 font-medium whitespace-pre-wrap">{review.comment || <span className="italic text-slate-400">No comment provided</span>}</p>
                    </div>
                  </div>
                  <button 
                    onClick={() => handleDelete(review.id)}
                    disabled={loading}
                    className="flex items-center justify-center p-3 rounded-xl text-red-500 hover:bg-red-50 hover:text-red-600 transition-colors"
                    title="Delete Review"
                  >
                    <Trash2 className="w-5 h-5" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

// Just for the empty state icon
function CheckCircle(props: any) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
      <polyline points="22 4 12 14.01 9 11.01" />
    </svg>
  );
}
