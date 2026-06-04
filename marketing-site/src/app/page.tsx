"use client";

import { useEffect, useState } from "react";
import { Download, Star, CheckCircle, Zap, Shield, ArrowRight, MessageSquare } from "lucide-react";

export default function Home() {
  const [stats, setStats] = useState<{
    downloads: number;
    thumbs_up: number;
    thumbs_down: number;
    recent_comments: { rating: string; comment: string; timestamp: string }[];
  } | null>(null);

  useEffect(() => {
    // Fetch live stats from backend
    const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "https://study-synthesizer.onrender.com";
    fetch(`${API_BASE_URL}/api/stats/summary`)
      .then(res => res.json())
      .then(data => setStats(data))
      .catch(err => console.error("Failed to fetch stats", err));
  }, []);

  const totalReviews = stats ? stats.thumbs_up + stats.thumbs_down : 0;
  const approvalRating = totalReviews > 0 ? Math.round((stats!.thumbs_up / totalReviews) * 100) : 100;

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans selection:bg-indigo-500/30">
      {/* Navbar */}
      <nav className="flex justify-between items-center p-6 max-w-6xl mx-auto">
        <div className="text-xl font-extrabold text-indigo-600 tracking-tight flex items-center space-x-2">
          <Zap className="w-6 h-6" />
          <span>StudySynthesizer</span>
        </div>
        <div className="space-x-6 text-sm font-semibold">
          <a href="#features" className="hover:text-indigo-600 transition-colors">Features</a>
          <a href="#reviews" className="hover:text-indigo-600 transition-colors">Reviews</a>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="max-w-6xl mx-auto px-6 pt-24 pb-32 text-center">
        <h1 className="text-6xl md:text-7xl font-extrabold tracking-tight text-slate-900 leading-tight mb-8">
          Turn any video into <br />
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 to-purple-600">
            perfect study notes.
          </span>
        </h1>
        <p className="text-xl text-slate-600 max-w-2xl mx-auto mb-10 leading-relaxed">
          Upload lectures, YouTube links, or documents and let our AI instantly generate deep-dive summaries, 1-line highlights, and mastery quizzes.
        </p>
        
        <div className="flex justify-center space-x-4 mb-16">
          <a href="https://github.com/surajms1415/Study-Synthesizer/releases/download/v1.0.0/StudySynthesizer.Setup.1.0.0.exe" className="flex items-center space-x-2 bg-indigo-600 text-white px-8 py-4 rounded-full font-bold text-lg hover:bg-indigo-700 hover:scale-105 transition-all shadow-xl shadow-indigo-600/30">
            <Download className="w-5 h-5" />
            <span>Download for Windows</span>
          </a>
          <a href="#" className="flex items-center space-x-2 bg-white text-slate-800 border border-slate-200 px-8 py-4 rounded-full font-bold text-lg hover:bg-slate-50 hover:scale-105 transition-all shadow-sm">
            <span>View on GitHub</span>
          </a>
        </div>

        {/* Live Stats */}
        <div className="flex justify-center items-center space-x-12 p-8 bg-white rounded-3xl shadow-xl shadow-slate-200/50 border border-slate-100 max-w-3xl mx-auto">
          <div className="text-center">
            <div className="text-4xl font-black text-indigo-600 mb-1">
              {stats ? stats.downloads.toLocaleString() : "..."}
            </div>
            <div className="text-sm font-semibold text-slate-500 uppercase tracking-widest">Notes Generated</div>
          </div>
          <div className="w-px h-16 bg-slate-200"></div>
          <div className="text-center">
            <div className="text-4xl font-black text-emerald-500 mb-1 flex items-center justify-center space-x-2">
              <span>{approvalRating}%</span>
              <Star className="w-6 h-6 fill-current" />
            </div>
            <div className="text-sm font-semibold text-slate-500 uppercase tracking-widest">User Satisfaction</div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="bg-white py-32 border-t border-slate-100">
        <div className="max-w-6xl mx-auto px-6">
          <h2 className="text-4xl font-bold text-center mb-16">Everything you need to ace your exams.</h2>
          <div className="grid md:grid-cols-3 gap-8">
            <div className="p-8 rounded-3xl bg-slate-50 border border-slate-100 hover:shadow-lg transition-shadow">
              <div className="w-12 h-12 bg-indigo-100 text-indigo-600 rounded-2xl flex items-center justify-center mb-6">
                <CheckCircle className="w-6 h-6" />
              </div>
              <h3 className="text-xl font-bold mb-3">Instant Deep Dives</h3>
              <p className="text-slate-600 leading-relaxed">
                We transcribe, analyze, and format hours of video content into clean, readable Markdown documents in seconds.
              </p>
            </div>
            <div className="p-8 rounded-3xl bg-slate-50 border border-slate-100 hover:shadow-lg transition-shadow">
              <div className="w-12 h-12 bg-purple-100 text-purple-600 rounded-2xl flex items-center justify-center mb-6">
                <Shield className="w-6 h-6" />
              </div>
              <h3 className="text-xl font-bold mb-3">Mastery Quizzes</h3>
              <p className="text-slate-600 leading-relaxed">
                Test your knowledge immediately. Our AI generates multiple-choice questions specifically targeted at the core concepts.
              </p>
            </div>
            <div className="p-8 rounded-3xl bg-slate-50 border border-slate-100 hover:shadow-lg transition-shadow">
              <div className="w-12 h-12 bg-emerald-100 text-emerald-600 rounded-2xl flex items-center justify-center mb-6">
                <Zap className="w-6 h-6" />
              </div>
              <h3 className="text-xl font-bold mb-3">1-Line Highlights</h3>
              <p className="text-slate-600 leading-relaxed">
                Short on time? Get the absolute bare-minimum facts you need to know in concise, one-sentence bullet points.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Reviews */}
      <section id="reviews" className="py-32 bg-slate-900 text-white overflow-hidden">
        <div className="max-w-4xl mx-auto px-6">
          <h2 className="text-4xl font-bold text-center mb-4">Loved by Students</h2>
          <p className="text-slate-400 text-center mb-16">Real feedback directly from the app.</p>
          
          <div className="relative h-[500px] overflow-hidden mask-image-vertical">
            {stats && stats.recent_comments.length > 0 ? (
              <div className="flex flex-col space-y-6 animate-marquee-vertical">
                {[...stats.recent_comments, ...stats.recent_comments].map((review, idx) => (
                  <div key={idx} className="bg-white/5 border border-white/10 p-8 rounded-3xl flex space-x-6 items-start shrink-0">
                    <div className={`p-3 rounded-full ${review.rating === 'up' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'}`}>
                      <MessageSquare className="w-6 h-6" />
                    </div>
                    <div>
                      <p className="text-lg leading-relaxed mb-3">"{review.comment}"</p>
                      <div className="flex items-center space-x-2 text-sm text-slate-400">
                        <span className="font-semibold text-white">Anonymous User</span>
                        <span>•</span>
                        <span>{new Date(review.timestamp).toLocaleDateString()}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center text-slate-500 p-8 bg-white/5 rounded-3xl h-full flex items-center justify-center">
                No reviews yet. Be the first to try it!
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-slate-950 text-slate-500 py-12 text-center">
        <p>© 2026 StudySynthesizer. Built for placement season.</p>
      </footer>
    </div>
  );
}
