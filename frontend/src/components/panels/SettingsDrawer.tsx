"use client";

import { useState } from "react";
import { X, PlugsConnected, Plugs } from "@phosphor-icons/react";
import { api } from "@/lib/api";

interface Props {
  open: boolean;
  onClose: () => void;
  mode: string;
}

export default function SettingsDrawer({ open, onClose, mode }: Props) {
  const [routerUrl, setRouterUrl] = useState("http://10.0.1.1");
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  const handleConnect = async () => {
    setLoading(true);
    setMessage("");
    try {
      const res = await api.ikuaiConnect({ routerUrl, username, password });
      setMessage(res.ok ? "连接成功" : `连接失败: ${res.error}`);
    } catch (e: any) {
      setMessage(`错误: ${e.message}`);
    }
    setLoading(false);
  };

  const handleDisconnect = async () => {
    setLoading(true);
    try {
      await api.ikuaiDisconnect();
      setMessage("已断开，恢复模拟数据");
    } catch (e: any) {
      setMessage(`错误: ${e.message}`);
    }
    setLoading(false);
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative z-10 flex w-80 flex-col border-l border-cyan-400/10 bg-[#03050a]/95 backdrop-blur-xl">
        <div className="flex items-center justify-between border-b border-cyan-400/10 px-4 py-3">
          <h2 className="text-sm font-semibold text-cyan-400">设置</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-200">
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 space-y-4 p-4">
          {/* 数据源 */}
          <div className="rounded-md border border-cyan-400/10 bg-base-800/40 p-3">
            <div className="mb-2 text-xs font-semibold text-slate-300">数据源</div>
            <div className="flex items-center gap-2 text-xs">
              {mode === "ikuai" ? (
                <>
                  <PlugsConnected size={16} className="text-emerald-400" />
                  <span className="text-emerald-400">iKuai 直连模式</span>
                </>
              ) : (
                <>
                  <Plugs size={16} className="text-slate-500" />
                  <span className="text-slate-400">模拟数据模式</span>
                </>
              )}
            </div>
          </div>

          {/* iKuai 连接表单 */}
          <div className="space-y-2">
            <label className="text-xs text-slate-500">路由器地址</label>
            <input
              value={routerUrl}
              onChange={(e) => setRouterUrl(e.target.value)}
              className="w-full rounded border border-cyan-400/15 bg-base-800/60 px-2.5 py-1.5 text-xs text-slate-200 outline-none focus:border-cyan-400/40"
              placeholder="http://10.0.1.1"
            />
            <label className="text-xs text-slate-500">用户名</label>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full rounded border border-cyan-400/15 bg-base-800/60 px-2.5 py-1.5 text-xs text-slate-200 outline-none focus:border-cyan-400/40"
            />
            <label className="text-xs text-slate-500">密码</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded border border-cyan-400/15 bg-base-800/60 px-2.5 py-1.5 text-xs text-slate-200 outline-none focus:border-cyan-400/40"
            />
            <div className="flex gap-2 pt-1">
              <button
                onClick={handleConnect}
                disabled={loading}
                className="flex-1 rounded bg-cyan-400/15 px-3 py-1.5 text-xs font-semibold text-cyan-400 transition-colors hover:bg-cyan-400/25 disabled:opacity-50"
              >
                {loading ? "连接中..." : "连接 iKuai"}
              </button>
              <button
                onClick={handleDisconnect}
                disabled={loading}
                className="rounded border border-slate-600/30 px-3 py-1.5 text-xs text-slate-400 transition-colors hover:text-slate-200 disabled:opacity-50"
              >
                断开
              </button>
            </div>
            {message && (
              <div className="text-[11px] text-slate-400">{message}</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
