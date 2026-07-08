import type { Context, Config } from "@netlify/functions";
import { getStore, getDeployStore } from "@netlify/blobs";
import seedData from "../../data.json" with { type: "json" };

const STORE_NAME = "financeos";
const KEY = "data.json";

function getBlobStore() {
  if (Netlify.context?.deploy?.context === "production") {
    return getStore(STORE_NAME);
  }
  return getDeployStore(STORE_NAME);
}

function isAuthorized(req: Request): boolean {
  const token = Netlify.env.get("DASHBOARD_TOKEN");
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
    return Response.json({ ok: true });
  }

  return new Response("Method Not Allowed", { status: 405 });
};

export const config: Config = {
  path: "/api/data"
};
