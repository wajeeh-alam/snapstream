(() => {
  const config = window.SNAPSTREAM_DEMO_CONFIG || {};
  const now = Date.now();
  const hoursAgo = (hours) => new Date(now - hours * 60 * 60 * 1000).toISOString();

  const users = [
    { id: "maya", username: "maya_frames", display_name: "Maya Chen" },
    { id: "noah", username: "noah_trails", display_name: "Noah Williams" },
    { id: "lina", username: "lina_builds", display_name: "Lina Haddad" },
    { id: "theo", username: "theo_tastes", display_name: "Theo Martin" },
    { id: "zoe", username: "zoe_afterdark", display_name: "Zoë Alvarez" },
    { id: "sam", username: "sam_onfilm", display_name: "Sam Okafor" },
  ];

  const demoUser = {
    ...users[0],
    email: "maya_frames@snapstream.demo",
    created_at: hoursAgo(24 * 90),
  };

  const media = (key) => ({
    bucket: "portfolio-demo",
    key,
    content_type: "image/svg+xml",
    size_bytes: 1,
  });

  const seedPosts = [
    { id: "morning-light", author: users[0], body: "Golden hour found us before the rain did.", likes_count: 42, created_at: hoursAgo(1), media: media("morning-light") },
    { id: "waterfall", author: users[1], body: "Six quiet miles, one very loud waterfall.", likes_count: 37, created_at: hoursAgo(3), media: media("waterfall") },
    { id: "accessibility", author: users[2], body: "The tiny accessibility detail that made today's build feel finished.", likes_count: 31, created_at: hoursAgo(5), media: null },
    { id: "sunday-table", author: users[3], body: "Sunday experiment: citrus, charred scallions, and zero leftovers.", likes_count: 29, created_at: hoursAgo(8), media: media("sunday-table") },
    { id: "blue-hour", author: users[4], body: "The city changes character after the last train.", likes_count: 26, created_at: hoursAgo(12), media: media("blue-hour") },
    { id: "film-green", author: users[5], body: "Shot a whole roll looking for this exact shade of green.", likes_count: 24, created_at: hoursAgo(17), media: media("film-green") },
    { id: "optimistic-heart", author: users[2], body: "Shipped the feed interaction states. The optimistic heart wins.", likes_count: 18, created_at: hoursAgo(22), media: null },
    { id: "phone-away", author: users[1], body: "Trail rule: take the photo, then put the phone away.", likes_count: 16, created_at: hoursAgo(29), media: media("phone-away") },
    { id: "ordinary-corners", author: users[0], body: "Proof that ordinary corners can still surprise you.", likes_count: 14, created_at: hoursAgo(35), media: media("ordinary-corners") },
    { id: "grain-motion", author: users[5], body: "Grain, motion, and a little bit of luck.", likes_count: 12, created_at: hoursAgo(43), media: media("grain-motion") },
  ];

  const themes = [
    ["#0f172a", "#38bdf8", "#fbbf24"],
    ["#172554", "#14b8a6", "#dbeafe"],
    ["#3f1d38", "#fb7185", "#fdba74"],
    ["#052e16", "#22c55e", "#bef264"],
    ["#2e1065", "#8b5cf6", "#f0abfc"],
  ];

  const storedPosts = () => {
    try {
      return JSON.parse(localStorage.getItem("snapstream_demo_posts") || "[]");
    } catch {
      return [];
    }
  };

  const allPosts = () => [...storedPosts(), ...seedPosts];
  const likedIds = () => new Set(JSON.parse(localStorage.getItem("snapstream_liked") || "[]"));
  const withLocalLikes = (post) => ({
    ...post,
    likes_count: post.likes_count + (likedIds().has(post.id) ? 1 : 0),
  });

  const artwork = (postId) => {
    const index = [...postId].reduce((sum, character) => sum + character.charCodeAt(0), 0);
    const [dark, color, accent] = themes[index % themes.length];
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 750">
      <defs>
        <linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop stop-color="${dark}"/><stop offset="1" stop-color="${color}"/></linearGradient>
        <filter id="b"><feGaussianBlur stdDeviation="70"/></filter>
      </defs>
      <rect width="1200" height="750" fill="url(#g)"/>
      <circle cx="930" cy="130" r="210" fill="${accent}" opacity=".78" filter="url(#b)"/>
      <circle cx="260" cy="690" r="270" fill="${color}" opacity=".65" filter="url(#b)"/>
      <path d="M0 610 C210 480 365 700 570 555 S930 405 1200 565 V750 H0Z" fill="${dark}" opacity=".58"/>
      <path d="M0 655 C260 535 430 720 675 585 S965 485 1200 610" fill="none" stroke="white" stroke-opacity=".3" stroke-width="3"/>
      <text x="56" y="74" fill="white" fill-opacity=".9" font-family="system-ui,sans-serif" font-size="24" font-weight="700" letter-spacing="5">SNAPSTREAM / SAMPLE</text>
    </svg>`;
    return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
  };

  const json = (value, status = 200) => new Response(JSON.stringify(value), {
    status,
    headers: { "Content-Type": "application/json" },
  });

  const nativeFetch = window.fetch.bind(window);
  window.fetch = async (input, options = {}) => {
    const requestUrl = new URL(typeof input === "string" ? input : input.url, window.location.href);
    const path = requestUrl.pathname;
    const method = (options.method || "GET").toUpperCase();

    if (path.endsWith("/config/public")) {
      return json({ public_demo: true, registration_enabled: false, uploads_enabled: false, static_demo: true });
    }
    if (path.endsWith("/health/ready")) return json({ status: "ok", checks: { demo: "ok" } });
    if (path.endsWith("/users")) return json(users);

    if (path.endsWith("/feed")) {
      const kind = requestUrl.searchParams.get("kind") === "trending" ? "trending" : "recent";
      const posts = allPosts().map(withLocalLikes);
      posts.sort(kind === "trending"
        ? (a, b) => b.likes_count - a.likes_count || new Date(b.created_at) - new Date(a.created_at)
        : (a, b) => new Date(b.created_at) - new Date(a.created_at));
      return json({ kind, items: posts });
    }

    if (path.endsWith("/posts") && method === "POST") {
      const payload = JSON.parse(options.body || "{}");
      const post = {
        id: `local-${Date.now()}`,
        author: users[0],
        body: String(payload.body || "").trim(),
        likes_count: 0,
        created_at: new Date().toISOString(),
        media: null,
      };
      const posts = storedPosts();
      posts.unshift(post);
      localStorage.setItem("snapstream_demo_posts", JSON.stringify(posts));
      return json(post, 201);
    }

    const likeMatch = path.match(/\/posts\/([^/]+)\/likes$/);
    if (likeMatch) {
      const post = allPosts().find((item) => item.id === likeMatch[1]);
      const liked = method !== "DELETE";
      return json({ post_id: likeMatch[1], likes_count: (post?.likes_count || 0) + (liked ? 1 : 0), liked });
    }

    const followMatch = path.match(/\/users\/([^/]+)\/follow$/);
    if (followMatch) return json({ user_id: followMatch[1], following: method !== "DELETE" });

    const mediaMatch = path.match(/\/posts\/([^/]+)\/media-url$/);
    if (mediaMatch) return json({ download_url: artwork(mediaMatch[1]), expires_in: 86400 });
    if (path.endsWith("/auth/logout")) return new Response(null, { status: 204 });

    return nativeFetch(input, options);
  };

  window.SNAPSTREAM_STATIC_DEMO = { user: demoUser };

  const contactLinks = document.querySelector("#contact-links");
  const contacts = [
    ["Portfolio", config.portfolio_url],
    ["GitHub", config.github_url],
    ["X", config.x_url],
    ["LinkedIn", config.linkedin_url],
  ].filter(([, url]) => url);
  contactLinks.innerHTML = contacts.map(([label, url]) =>
    `<a href="${url}" target="_blank" rel="noopener noreferrer">${label} ↗</a>`
  ).join("");

  document.querySelectorAll('a[href="/docs"]').forEach((link) => {
    link.href = `${config.github_url || "https://github.com/wajeeh-alam/snapstream"}#api-flow`;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = "View source";
  });
})();
