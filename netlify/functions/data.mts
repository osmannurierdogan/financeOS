import type { Context, Config } from "@netlify/functions";
import { getStore, getDeployStore } from "@netlify/blobs";
import seedData from "../../data.json" with { type: "json" };
import fs from "node:fs";
import path from "node:path";

const STORE_NAME = "financeos";
const KEY = "data.json";

// Read local .env.local if it exists
let localToken = "";
try {
  const cwd = process.cwd();
  const envPath = cwd.endsWith("/public") || cwd.endsWith("\\public")
    ? path.resolve(cwd, "..", ".env.local")
    : path.resolve(cwd, ".env.local");
  if (fs.existsSync(envPath)) {
    const envContent = fs.readFileSync(envPath, "utf-8");
    const match = envContent.match(/^DASHBOARD_TOKEN\s*=\s*(.*)$/m);
    if (match) {
      localToken = match[1].trim().replace(/^['"]|['"]$/g, "");
    }
  }
} catch (e) {}

function getBlobStore() {
  if (Netlify.context?.deploy?.context === "production") {
    return getStore(STORE_NAME);
  }
  return getDeployStore(STORE_NAME);
}

function isAuthorized(req: Request): boolean {
  const token = Netlify.env.get("DASHBOARD_TOKEN") || process.env.DASHBOARD_TOKEN || localToken;
  if (!token) return false; // fail closed if misconfigured
  const auth = req.headers.get("authorization") || "";
  return auth === `Bearer ${token}`;
}

export default async (req: Request, context: Context) => {
  if (!isAuthorized(req)) {
    return new Response("Unauthorized", { status: 401 });
  }

  const store = getBlobStore();

  if (req.method === "GET") {
    const existing = await store.get(KEY, { type: "json" });
    return Response.json(existing ?? seedData);
  }

  if (req.method === "POST" || req.method === "PUT") {
    let body: any;
    try {
      body = await req.json();
    } catch {
      return new Response("Invalid JSON body", { status: 400 });
    }
    if (!body || typeof body !== "object" || !body.snapshot) {
      return new Response("Missing snapshot in body", { status: 400 });
    }
    await store.setJSON(KEY, body);

    // In local development, write to both root and public data.json to keep them in sync
    if (Netlify.context?.deploy?.context !== "production") {
      try {
        const cwd = process.cwd();
        const pathsToSync = [];
        
        if (cwd.endsWith("/public") || cwd.endsWith("\\public")) {
          pathsToSync.push(path.resolve(cwd, "data.json"));
          pathsToSync.push(path.resolve(cwd, "..", "data.json"));
        } else {
          pathsToSync.push(path.resolve(cwd, "data.json"));
          pathsToSync.push(path.resolve(cwd, "public", "data.json"));
        }
        
        for (const p of pathsToSync) {
          try {
            fs.writeFileSync(p, JSON.stringify(body, null, 2), "utf-8");
          } catch (e) {}
        }
      } catch (err) {
        console.error("Failed to write to local data.json files:", err);
      }
    }

    return Response.json({ ok: true });
  }

  return new Response("Method Not Allowed", { status: 405 });
};

export const config: Config = {
  path: "/api/data"
};
