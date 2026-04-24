const userForm = document.getElementById("user-form");
const orderForm = document.getElementById("order-form");
const userResult = document.getElementById("user-result");
const orderResult = document.getElementById("order-result");
const selectedUserEl = document.getElementById("selected-user");
const walletBalanceEl = document.getElementById("wallet-balance");
const marketGrid = document.getElementById("market-grid");
const portfolioBody = document.getElementById("portfolio-body");
const ordersBody = document.getElementById("orders-body");
const eventsFeed = document.getElementById("events-feed");
const refreshButton = document.getElementById("refresh-all");
const orderUserIdInput = document.getElementById("order-user-id");

const state = {
  selectedUserId: Number(localStorage.getItem("trading_selected_user_id")) || null,
  socket: null,
};

function formatCurrency(value) {
  const amount = Number(value ?? 0);
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(amount);
}

function setSelectedUser(user) {
  state.selectedUserId = user?.id ?? null;
  if (state.selectedUserId) {
    localStorage.setItem("trading_selected_user_id", String(state.selectedUserId));
    orderUserIdInput.value = String(state.selectedUserId);
    selectedUserEl.textContent = `${user.name} (#${user.id})`;
    walletBalanceEl.textContent = `Wallet: ${formatCurrency(user.wallet.balance)}`;
    connectWebSocket(state.selectedUserId);
  } else {
    localStorage.removeItem("trading_selected_user_id");
    selectedUserEl.textContent = "None";
    walletBalanceEl.textContent = "Wallet: --";
  }
}

function renderMarket(prices) {
  marketGrid.innerHTML = prices
    .map(
      (item) => `
        <article class="market-card">
          <div class="symbol">${item.symbol}</div>
          <div class="price">${formatCurrency(item.price)}</div>
        </article>
      `,
    )
    .join("");
}

function renderPortfolio(items) {
  if (!items.length) {
    portfolioBody.innerHTML =
      '<tr><td colspan="5" class="empty-cell">No open positions.</td></tr>';
    return;
  }

  portfolioBody.innerHTML = items
    .map((item) => {
      const pnl = Number(item.unrealized_pnl);
      const pnlClass = pnl >= 0 ? "profit" : "loss";
      return `
        <tr>
          <td>${item.symbol}</td>
          <td>${item.quantity}</td>
          <td>${formatCurrency(item.average_price)}</td>
          <td>${formatCurrency(item.current_price)}</td>
          <td class="${pnlClass}">${formatCurrency(item.unrealized_pnl)}</td>
        </tr>
      `;
    })
    .join("");
}

function renderOrders(items) {
  if (!items.length) {
    ordersBody.innerHTML =
      '<tr><td colspan="7" class="empty-cell">No orders found for this user.</td></tr>';
    return;
  }

  ordersBody.innerHTML = items
    .map(
      (item) => `
        <tr>
          <td>${item.id}</td>
          <td>${item.symbol}</td>
          <td>${item.qty}</td>
          <td>${item.side}</td>
          <td>${formatCurrency(item.price)}</td>
          <td>${item.status}</td>
          <td>${new Date(item.created_at).toLocaleString()}</td>
        </tr>
      `,
    )
    .join("");
}

function addEvent(message) {
  const empty = eventsFeed.querySelector(".muted");
  if (empty) empty.remove();
  const item = document.createElement("div");
  item.className = "event-item";
  item.textContent = message;
  eventsFeed.prepend(item);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });

  if (!response.ok) {
    let detail = "Request failed";
    try {
      const payload = await response.json();
      detail = payload.detail || JSON.stringify(payload);
    } catch {
      detail = await response.text();
    }
    throw new Error(detail);
  }

  if (response.status === 204) return null;
  return response.json();
}

async function loadUser(userId) {
  const user = await api(`/users/${userId}`);
  setSelectedUser(user);
  return user;
}

async function loadDashboard() {
  await loadMarket();
  if (!state.selectedUserId) return;
  const [user, portfolio, orders] = await Promise.all([
    loadUser(state.selectedUserId),
    api(`/portfolio/${state.selectedUserId}`),
    api(`/orders/${state.selectedUserId}`),
  ]);
  setSelectedUser(user);
  renderPortfolio(portfolio);
  renderOrders(orders);
}

async function loadMarket() {
  const prices = await api("/market/prices");
  renderMarket(prices);
}

function connectWebSocket(userId) {
  if (state.socket) {
    state.socket.close();
  }

  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(`${protocol}://${window.location.host}/ws/${userId}`);
  state.socket = socket;

  socket.onopen = () => addEvent(`Connected to live updates for user #${userId}.`);
  socket.onmessage = async (event) => {
    const payload = JSON.parse(event.data);
    walletBalanceEl.textContent = `Wallet: ${formatCurrency(payload.wallet_balance)}`;
    addEvent(
      `${payload.side} ${payload.qty} ${payload.symbol} at ${formatCurrency(payload.price)} (${payload.status})`,
    );
    await loadDashboard();
  };
  socket.onclose = () => addEvent(`Live updates disconnected for user #${userId}.`);
}

userForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(userForm);
  try {
    const user = await api("/users", {
      method: "POST",
      body: JSON.stringify({
        name: formData.get("name"),
        email: formData.get("email"),
      }),
    });
    const hasActiveSelection = Boolean(state.selectedUserId);
    if (!hasActiveSelection) {
      setSelectedUser(user);
      await loadDashboard();
      userResult.textContent = `Created ${user.name} with user ID ${user.id} and wallet ${formatCurrency(user.wallet.balance)}. This user is now selected.`;
    } else {
      orderUserIdInput.value = String(user.id);
      userResult.textContent = `Created ${user.name} with user ID ${user.id} and wallet ${formatCurrency(user.wallet.balance)}. Current preview user was kept unchanged.`;
      await loadMarket();
    }
    userForm.reset();
  } catch (error) {
    userResult.textContent = error.message;
  }
});

orderForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(orderForm);
  try {
    const order = await api("/orders", {
      method: "POST",
      body: JSON.stringify({
        user_id: Number(formData.get("user_id")),
        symbol: formData.get("symbol"),
        qty: Number(formData.get("qty")),
        side: formData.get("side"),
      }),
    });
    orderResult.textContent = `Order #${order.id} executed: ${order.side} ${order.qty} ${order.symbol} at ${formatCurrency(order.price)}.`;
    if (!state.selectedUserId || state.selectedUserId !== order.user_id) {
      await loadUser(order.user_id);
    }
    await loadDashboard();
  } catch (error) {
    orderResult.textContent = error.message;
  }
});

refreshButton.addEventListener("click", async () => {
  try {
    await loadDashboard();
  } catch (error) {
    addEvent(`Refresh failed: ${error.message}`);
  }
});

loadDashboard().catch((error) => {
  addEvent(`Initial load issue: ${error.message}`);
});
