const SYSTEM_PROMPT = `You are WanderWise, an elite, highly knowledgeable trip-planning expert and global travel consultant.
Your mission is to help travelers build unforgettable, practical, well-structured, and realistic travel itineraries.

Guidelines for your responses:
1. STRUCTURE & CLARITY: Organize itineraries with clear day-by-day breakdowns, headings, and bullet points.
2. COMPREHENSIVE PLANNING: Include recommendations for sights, local culinary gems, transportation logistics, estimated budget ranges, and pacing.
3. CULTURAL & PRACTICAL TIPS: Include local cultural etiquette, safety considerations, best seasons/times to visit, and essential packing suggestions.
4. PERSONALIZATION: Tailor advice to the user's travel style (solo, couple, family, backpacker, luxury).
5. TONE: Warm, inspiring, organized, and encouraging.`;

function sanitizeError(msg, apiKey) {
  if (!msg) return "An unexpected error occurred.";
  let sanitized = String(msg);
  if (apiKey && apiKey.length > 4) {
    sanitized = sanitized.split(apiKey).join("[REDACTED_API_KEY]");
  }
  sanitized = sanitized.replace(/Bearer\s+[A-Za-z0-9_\-\.]+/gi, "Bearer [REDACTED]");
  sanitized = sanitized.replace(/api-key:\s*[A-Za-z0-9_\-\.]+/gi, "api-key: [REDACTED]");
  return sanitized;
}

exports.handler = async function(event, context) {
  // Handle CORS Preflight
  if (event.httpMethod === "OPTIONS") {
    return {
      statusCode: 200,
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
      },
      body: "",
    };
  }

  if (event.httpMethod !== "POST") {
    return {
      statusCode: 405,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ detail: "Method Not Allowed. Use POST." }),
    };
  }

  const endpoint = (process.env.AZURE_ENDPOINT || "").trim();
  const apiKey = (process.env.AZURE_API_KEY || "").trim();
  const deployment = (
    process.env.AZURE_DEPLOYMENT ||
    process.env.AZURE_DEPLOYMENT_NAME ||
    process.env.ZURE_DEPLOYMENT_NAME ||
    "gpt-5-mini"
  ).trim();
  const apiVersion = (process.env.AZURE_API_VERSION || "2024-06-01").trim();

  if (!endpoint || !apiKey) {
    return {
      statusCode: 500,
      headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
      body: JSON.stringify({
        detail: "Missing AZURE_ENDPOINT or AZURE_API_KEY in Netlify Environment Variables.",
      }),
    };
  }

  let requestBody;
  try {
    requestBody = JSON.parse(event.body || "{}");
  } catch (err) {
    return {
      statusCode: 400,
      headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
      body: JSON.stringify({ detail: "Invalid JSON body." }),
    };
  }

  const incomingMessages = requestBody.messages || [];
  if (!Array.isArray(incomingMessages) || incomingMessages.length === 0) {
    return {
      statusCode: 400,
      headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
      body: JSON.stringify({ detail: "Messages list cannot be empty." }),
    };
  }

  // Prepend ONE system message
  const messages = [{ role: "system", content: SYSTEM_PROMPT }];
  for (const m of incomingMessages) {
    if (m.role && m.role.toLowerCase() === "system") continue;
    messages.push({
      role: m.role && m.role.toLowerCase() === "assistant" ? "assistant" : "user",
      content: m.content || "",
    });
  }

  // Extract base host from endpoint
  let host = endpoint;
  try {
    const u = new URL(endpoint);
    host = `${u.protocol}//${u.host}`;
  } catch (e) {
    host = endpoint.replace(/\/api\/projects\/.*$/, "").replace(/\/+$/, "");
  }

  const url = `${host}/openai/deployments/${encodeURIComponent(deployment)}/chat/completions?api-version=${encodeURIComponent(apiVersion)}`;

  try {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "api-key": apiKey,
      },
      body: JSON.stringify({
        messages: messages,
        max_completion_tokens: 16000,
      }),
    });

    const data = await response.json();

    if (!response.ok) {
      const rawErrMsg = (data.error && data.error.message) || JSON.stringify(data);
      const sanitized = sanitizeError(rawErrMsg, apiKey);
      return {
        statusCode: response.status,
        headers: {
          "Content-Type": "application/json",
          "Access-Control-Allow-Origin": "*",
        },
        body: JSON.stringify({ detail: `Azure AI Error: ${sanitized}` }),
      };
    }

    const choice = data.choices && data.choices[0];
    const reply = (choice && choice.message && choice.message.content) || "";

    if (!reply && choice && choice.finish_reason === "length") {
      return {
        statusCode: 200,
        headers: {
          "Content-Type": "application/json",
          "Access-Control-Allow-Origin": "*",
        },
        body: JSON.stringify({
          reply: "⚠️ The response required deep reasoning and reached the token limit. Please try asking a more specific question or breaking down your itinerary request!",
        }),
      };
    }

    return {
      statusCode: 200,
      headers: {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
      },
      body: JSON.stringify({ reply: reply || "I couldn't generate a response for this prompt. Please try rephrasing your trip details." }),
    };
  } catch (err) {
    const sanitized = sanitizeError(err.message, apiKey);
    return {
      statusCode: 500,
      headers: {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
      },
      body: JSON.stringify({ detail: `Server error: ${sanitized}` }),
    };
  }
};
