import { serve } from "https://deno.land/std@0.203.0/http/server.ts";
let gmail_tool = {
  name: "gmail_create_draft",
  description: "Creates a Gmail draft",
  google_account: "tariksagbas1@gmail.com",
  inputs: {
    to: { type: "string" },
    subject: { type: "string" },
    body: { type: "string" },
    bcc: { type: "string" },
    cc: { type: "string" }
  },
  outputs: {
    draftId: { type: "string" }
  }
};

const CLIENT_ID     = "60187015874-b3pa6e7fg5ot8g6qtfpa4l5bp433jh97.apps.googleusercontent.com";
const CLIENT_SECRET = "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";
const REFRESH_TOKEN = "1//04qCgWDtAsrjlCgYIARAAGAQSNwF-L9Ir_lpW8fNxQvCuSdQBN6BK6cu1_h0rNMUaVpeTaQ2pIwHzjC_bQZHO_DyI2kYUkH2CC-Q";

const CONFIG = {
  serverName: "Icron_mcp_server",
  tools: [gmail_tool]
};

serve(async (req)=>{
  const url = new URL(req.url);
  console.log("▶️FULL REQUEST", req, req.method, url.pathname, "headers:", Object.fromEntries(req.headers));
  const { pathname, searchParams } = new URL(req.url);
  const accept = req.headers.get("accept") || "";

  // 1) SSE Response, Config (for Cursor)
  if (req.method === "GET" && accept.includes("text/event-stream")) {
    const payload = JSON.stringify(CONFIG);
    const body = `event: config\ndata: ${payload}\n\n`;
    return new Response(body, {
      status: 200,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Access-Control-Allow-Origin": "*"
      }
    });
  }

  // 2) Json Response, Config (for curl and other Agents)
  if (req.method === "GET") {
    return new Response(JSON.stringify(CONFIG), {
      status: 200,
      headers: {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*"
      }
    });
  }

  // 3) POST 
  if (req.method === "POST") {
    console.log("Tools");
    const { tool, input } = await req.json();

    if (tool === "gmail_create_draft") {
      try {
        const { to, subject, body, cc, bcc } = input;

        const tokenRes = await fetch("https://oauth2.googleapis.com/token", {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: new URLSearchParams({
              client_id:     CLIENT_ID,
              client_secret: CLIENT_SECRET,
              grant_type:    "refresh_token",
              refresh_token: REFRESH_TOKEN
            })
          });
        if (!tokenRes.ok) throw new Error("Failed to refresh token");
        const { access_token } = await tokenRes.json();


        const lines = [
            `To: ${to}`,
            cc  ? `Cc: ${cc}`   : "",
            bcc ? `Bcc: ${bcc}` : "",
            `Subject: ${subject}`,
            "",
            body
        ].filter(Boolean).join("\r\n");

        const raw = btoa(lines)
            .replace(/\+/g, "-")
            .replace(/\//g, "_")
            .replace(/=+$/, "");


           // 3) Call Gmail’s drafts.create
        const draftRes = await fetch(
            "https://gmail.googleapis.com/gmail/v1/users/me/drafts",
            {
            method: "POST",
            headers: {
                Authorization: `Bearer ${access_token}`,
                "Content-Type":  "application/json"
            },
            body: JSON.stringify({ message: { raw } })
            }
        );

        if (!draftRes.ok) {
            const errBody = await draftRes.text();
            console.error("Gmail draft error:", draftRes.status, errBody);
            return new Response(
              JSON.stringify({
                error:    "Gmail API error",
                status:   draftRes.status,
                details:  errBody
              }),
              { status: 500, headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" } }
            );
          }
          const { id: draftId } = await draftRes.json();

        return new Response(JSON.stringify({ draftId }), {
            status: 200,
            headers: {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            }
        });
    } catch(err) {
        console.error(err);
    return new Response(
      JSON.stringify({ error: (err as Error).message }),
      { status: 500, headers: { "Content-Type": "application/json" } }
    );
    }
    }
    else {
        return new Response(JSON.stringify({ error: "Tool not found" }), {
            status: 404,
            headers: {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            }
        })
    }
  }

  // Fallback 404
  return new Response("Not Found", { status: 404 });
});
