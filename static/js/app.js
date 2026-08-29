const state = {
    tarefas: [],
    todas: [],
    arquivadas: [],
    categorias: [],
    hoje: { atrasadas: [], hoje: [], concluidas: [] },
    view: "dashboard",
    editingId: null,
    editingCategoryId: null,
    detailsId: null,
    pendingActions: new Set(),
    pendingDeletes: new Map(),
    confirmHandler: null,
    authMode: "login",
    currentUser: null,
    onboardingStep: 0,
    calendarMonth: new Date(new Date().getFullYear(), new Date().getMonth(), 1),
    calendarSelected: null,
    csrfToken: document.querySelector('meta[name="csrf-token"]')?.content || "",
};

const ids = [
    "sidebar", "sidebarOverlay", "menuToggle", "pageEyebrow", "pageTitle", "searchInput", "newTaskButton",
    "summarySection", "dashboardInsights", "totalCount", "pendingCount", "completedCount", "overdueCount",
    "todayCount", "weekCount", "completionRate", "importantTasks", "recentCompleted", "navTodayCount",
    "navPendingCount", "navOverdueCount", "tasksPanel", "listTitle", "resultCount", "tasksGrid", "filterToggle",
    "filtersPanel", "statusFilter", "priorityFilter", "categoryFilter", "sortFilter", "clearFilters",
    "calendarPanel", "calendarTitle", "calendarGrid", "previousMonth", "nextMonth", "selectedDayTitle",
    "selectedDayTasks", "categoriesPanel", "categoriesGrid", "newCategoryButton", "dataPanel", "exportBackupButton",
    "restoreBackupInput", "connectionStatus", "sessionUser", "sessionUsername", "sessionInitial", "logoutButton",
    "authModal", "authForm", "authEyebrow", "authTitle", "authCopy", "authUsername", "authPassword",
    "authConfirmGroup", "authPasswordConfirm", "authError", "authSubmit", "authSwitch", "taskModal", "taskForm",
    "modalEyebrow", "modalTitle", "taskTitle", "taskDescription", "taskCategory", "taskPriority", "taskDeadline",
    "saveTaskButton", "detailsModal", "detailsTitle", "detailsCategory", "detailsPriority", "detailsStatus",
    "detailsDescription", "detailsCreatedAt", "detailsDeadline", "detailsCompletedGroup", "detailsCompletedAt",
    "detailsArchivedGroup", "detailsArchivedAt", "detailsEdit", "detailsDuplicate", "detailsComplete", "detailsArchive",
    "detailsRestore", "detailsDelete", "closeDetailsX", "closeDetailsButton", "categoryModal", "categoryForm",
    "categoryModalEyebrow", "categoryModalTitle", "categoryName", "categoryColor", "categoryIcon", "saveCategoryButton",
    "confirmModal", "confirmTitle", "confirmMessage", "cancelConfirm", "confirmAction", "onboardingModal",
    "onboardingIcon", "onboardingTitle", "onboardingCopy", "onboardingDots", "skipOnboarding", "nextOnboarding",
    "toastRegion",
];
const elements = Object.fromEntries(ids.map((id) => [id, document.querySelector(`#${id}`)]));
elements.navItems = document.querySelectorAll(".nav-item");
elements.searchBox = elements.searchInput.closest(".search-box");

const viewLabels = {
    dashboard: ["Visão geral", "Minhas Tarefas", "Tarefas recentes"],
    hoje: ["Planejamento diário", "Hoje", "Seu dia em foco"],
    calendario: ["Visão mensal", "Calendário", "Tarefas por prazo"],
    todas: ["Organização", "Todas as Tarefas", "Todas as tarefas"],
    pendentes: ["Em andamento", "Tarefas Pendentes", "Aguardando conclusão"],
    concluidas: ["Progresso", "Tarefas Concluídas", "Trabalho finalizado"],
    atrasadas: ["Atenção", "Tarefas Atrasadas", "Precisam de atenção"],
    categorias: ["Organização", "Categorias", "Categorias personalizadas"],
    arquivadas: ["Histórico", "Tarefas Arquivadas", "Arquivadas por até 30 dias"],
    dados: ["Seus dados", "Backup", "Exportar e restaurar"],
};

const onboardingPages = [
    { icon: "✓", title: "Organize suas tarefas", copy: "Centralize seus compromissos em um painel simples e claro." },
    { icon: "◆", title: "Priorize e acompanhe prazos", copy: "Use prioridades, categorias, a página Hoje e o calendário para manter o foco." },
    { icon: "＋", title: "Crie sua primeira tarefa", copy: "Você está pronto. Comece adicionando o que precisa fazer." },
];

async function api(path, options = {}) {
    const { headers = {}, ...requestOptions } = options;
    const method = (requestOptions.method || "GET").toUpperCase();
    const needsCsrf = ["POST", "PUT", "PATCH", "DELETE"].includes(method);
    const response = await fetch(path, {
        ...requestOptions,
        headers: {
            Accept: "application/json",
            ...(requestOptions.body ? { "Content-Type": "application/json" } : {}),
            ...(needsCsrf && state.csrfToken ? { "X-CSRFToken": state.csrfToken } : {}),
            ...headers,
        },
    });
    const data = response.status === 204 ? null : await response.json().catch(() => null);
    if (!response.ok) {
        const error = new Error(data?.erro || "Não foi possível completar a operação.");
        error.status = response.status;
        throw error;
    }
    return data;
}

function updateCsrfToken(token) {
    if (!token) return;
    state.csrfToken = token;
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta) meta.content = token;
}

function escapeHTML(value) {
    const element = document.createElement("div");
    element.textContent = value ?? "";
    return element.innerHTML.replaceAll('"', "&quot;").replaceAll("'", "&#39;");
}

function capitalize(value) {
    const labels = { media: "Média", baixa: "Baixa", alta: "Alta", pendente: "Pendente", concluida: "Concluída" };
    return labels[value] || value;
}

function localToday() {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

function formatDate(value) {
    if (!value) return "Sem prazo definido";
    return new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "short", year: "numeric" })
        .format(new Date(`${value}T00:00:00`)).replace(" de ", " ");
}

function formatDetailDate(value) {
    if (!value) return "Não definida";
    const parsed = new Date(value.length === 10 ? `${value}T00:00:00` : value);
    return new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" }).format(parsed);
}

function taskById(id) {
    const todayTasks = [...state.hoje.atrasadas, ...state.hoje.hoje, ...state.hoje.concluidas];
    return [...state.todas, ...state.arquivadas, ...todayTasks].find((task) => task.id === id);
}

function matchesSearch(task) {
    const search = elements.searchInput.value.trim().toLocaleLowerCase("pt-BR");
    if (!search) return true;
    return [task.titulo, task.descricao, task.categoria]
        .filter(Boolean)
        .some((value) => value.toLocaleLowerCase("pt-BR").includes(search));
}

function categoryByName(name) {
    return state.categorias.find((item) => item.nome.toLocaleLowerCase("pt-BR") === (name || "").toLocaleLowerCase("pt-BR"));
}

function setConnection(online) {
    elements.connectionStatus.classList.toggle("offline", !online);
    elements.connectionStatus.querySelector("strong").textContent = online ? "API conectada" : "API indisponível";
    elements.connectionStatus.querySelector("small").textContent = online ? "Dados sincronizados" : "Verifique o servidor";
}

function setAuthenticatedUser(user) {
    state.currentUser = user;
    elements.sessionUsername.textContent = user.nome;
    elements.sessionInitial.textContent = user.nome.charAt(0) || "U";
    elements.sessionUser.hidden = false;
}

function setAuthMode(mode) {
    state.authMode = mode;
    const registering = mode === "register";
    elements.authEyebrow.textContent = registering ? "Criar conta" : "Bem-vindo";
    elements.authTitle.textContent = registering ? "Comece a organizar" : "Entre na sua conta";
    elements.authCopy.textContent = registering ? "Crie um acesso para manter suas tarefas privadas." : "Use seu usuário e senha para continuar.";
    elements.authConfirmGroup.hidden = !registering;
    elements.authPasswordConfirm.required = registering;
    elements.authPassword.autocomplete = registering ? "new-password" : "current-password";
    elements.authSubmit.textContent = registering ? "Criar conta" : "Entrar";
    elements.authSwitch.textContent = registering ? "Já tenho uma conta" : "Ainda não tenho uma conta";
    elements.authError.textContent = "";
}

function closeApplicationDialogs() {
    [elements.taskModal, elements.detailsModal, elements.categoryModal, elements.confirmModal, elements.onboardingModal]
        .forEach((modal) => { if (modal.open) modal.close(); });
}

function showAuth(mode = "login") {
    setAuthMode(mode);
    state.currentUser = null;
    elements.sessionUser.hidden = true;
    closeApplicationDialogs();
    elements.authPassword.value = "";
    elements.authPasswordConfirm.value = "";
    if (!elements.authModal.open) elements.authModal.showModal();
    window.setTimeout(() => elements.authUsername.focus(), 50);
}

async function initializeSession() {
    try {
        const data = await api("/sessao");
        updateCsrfToken(data.csrf_token);
        if (!data.autenticado) return showAuth();
        setAuthenticatedUser(data.usuario);
        await loadBaseData();
        if (!data.usuario.onboarding_concluido) showOnboarding();
    } catch (_error) {
        setConnection(false);
        showAuth();
        elements.authError.textContent = "Não foi possível conectar ao servidor.";
    }
}

async function submitAuth(event) {
    event.preventDefault();
    elements.authError.textContent = "";
    const username = elements.authUsername.value.trim();
    const password = elements.authPassword.value;
    if (state.authMode === "register" && password !== elements.authPasswordConfirm.value) {
        elements.authError.textContent = "As senhas não coincidem.";
        return;
    }
    const originalLabel = elements.authSubmit.textContent;
    elements.authSubmit.disabled = true;
    elements.authSwitch.disabled = true;
    elements.authSubmit.textContent = state.authMode === "register" ? "Criando..." : "Entrando...";
    try {
        const data = await api(state.authMode === "register" ? "/usuarios" : "/login", {
            method: "POST", body: JSON.stringify({ usuario: username, senha: password }),
        });
        updateCsrfToken(data.csrf_token);
        setAuthenticatedUser(data.usuario);
        elements.authModal.close();
        elements.authForm.reset();
        showToast(state.authMode === "register" ? "Conta criada com sucesso." : "Login realizado com sucesso.");
        await loadBaseData();
        if (!data.usuario.onboarding_concluido) showOnboarding();
    } catch (error) {
        elements.authError.textContent = error.message;
    } finally {
        elements.authSubmit.disabled = false;
        elements.authSwitch.disabled = false;
        elements.authSubmit.textContent = originalLabel;
    }
}

async function finalizePendingDeletes() {
    const entries = [...state.pendingDeletes.entries()];
    entries.forEach(([, item]) => window.clearTimeout(item.timer));
    await Promise.allSettled(entries.map(([id]) => api(`/tarefas/${id}`, { method: "DELETE" })));
    state.pendingDeletes.clear();
}

async function logout() {
    if (state.pendingActions.has("logout")) return;
    state.pendingActions.add("logout");
    elements.logoutButton.disabled = true;
    try {
        await finalizePendingDeletes();
        const data = await api("/logout", { method: "POST" });
        updateCsrfToken(data.csrf_token);
        state.tarefas = [];
        state.todas = [];
        state.categorias = [];
        renderSummary();
        renderTasks();
        showAuth();
    } catch (error) {
        showToast(error.message, "error");
    } finally {
        state.pendingActions.delete("logout");
        elements.logoutButton.disabled = false;
    }
}

function renderLoading() {
    elements.resultCount.textContent = "Carregando suas tarefas...";
    elements.tasksGrid.innerHTML = Array.from({ length: 3 }, () => '<article class="task-card skeleton-card"><span></span><span></span><span></span></article>').join("");
}

function updateCategoryOptions() {
    const filterSelected = elements.categoryFilter.value;
    const taskSelected = elements.taskCategory.value;
    const filterFragment = document.createDocumentFragment();
    const taskFragment = document.createDocumentFragment();
    [[filterFragment, "Todas"], [taskFragment, "Sem categoria"]].forEach(([fragment, label]) => {
        const option = document.createElement("option");
        option.value = "";
        option.textContent = label;
        fragment.appendChild(option);
    });
    state.categorias.forEach((category) => {
        [filterFragment, taskFragment].forEach((fragment) => {
            const option = document.createElement("option");
            option.value = category.nome;
            option.textContent = `${category.icone ? `${category.icone} ` : ""}${category.nome}`;
            fragment.appendChild(option);
        });
    });
    elements.categoryFilter.replaceChildren(filterFragment);
    elements.taskCategory.replaceChildren(taskFragment);
    if (state.categorias.some((item) => item.nome === filterSelected)) elements.categoryFilter.value = filterSelected;
    if (state.categorias.some((item) => item.nome === taskSelected)) elements.taskCategory.value = taskSelected;
}

function renderSummary() {
    const pending = state.todas.filter((task) => task.status === "pendente").length;
    const completed = state.todas.filter((task) => task.status === "concluida").length;
    const overdue = state.todas.filter((task) => task.atrasada).length;
    const today = localToday();
    const todayPending = state.todas.filter((task) => task.status === "pendente" && task.data_limite === today).length;
    elements.totalCount.textContent = state.todas.length;
    elements.pendingCount.textContent = pending;
    elements.completedCount.textContent = completed;
    elements.overdueCount.textContent = overdue;
    elements.navTodayCount.textContent = todayPending + overdue;
    elements.navPendingCount.textContent = pending;
    elements.navOverdueCount.textContent = overdue;
}

function miniTaskTemplate(task) {
    return `<button class="mini-task" type="button" data-mini-task="${Number(task.id)}"><span><strong>${escapeHTML(task.titulo)}</strong><small>${escapeHTML(task.categoria || capitalize(task.prioridade))}</small></span><time>${escapeHTML(formatDate(task.data_limite))}</time></button>`;
}

function renderDashboard() {
    const today = new Date(`${localToday()}T00:00:00`);
    const weekEnd = new Date(today);
    weekEnd.setDate(weekEnd.getDate() + 7);
    const pendingToday = state.todas.filter((task) => task.status === "pendente" && task.data_limite === localToday()).length;
    const week = state.todas.filter((task) => {
        if (task.status !== "pendente" || !task.data_limite) return false;
        const deadline = new Date(`${task.data_limite}T00:00:00`);
        return deadline >= today && deadline <= weekEnd;
    }).length;
    const completed = state.todas.filter((task) => task.status === "concluida").length;
    elements.todayCount.textContent = pendingToday;
    elements.weekCount.textContent = week;
    elements.completionRate.textContent = state.todas.length ? `${Math.round((completed / state.todas.length) * 100)}%` : "0%";

    const important = state.todas.filter((task) => task.status === "pendente" && task.prioridade === "alta")
        .sort((a, b) => (a.data_limite || "9999-12-31").localeCompare(b.data_limite || "9999-12-31")).slice(0, 3);
    const recent = state.todas.filter((task) => task.status === "concluida")
        .sort((a, b) => new Date(b.data_conclusao) - new Date(a.data_conclusao)).slice(0, 3);
    elements.importantTasks.innerHTML = important.length ? important.map(miniTaskTemplate).join("") : '<p class="muted-copy">Nenhuma tarefa urgente no momento.</p>';
    elements.recentCompleted.innerHTML = recent.length ? recent.map(miniTaskTemplate).join("") : '<p class="muted-copy">As tarefas concluídas aparecerão aqui.</p>';
}

function visibleTasks(source = state.view === "arquivadas" ? state.arquivadas : state.tarefas) {
    let tasks = source.filter(matchesSearch);
    if (state.view === "pendentes") tasks = tasks.filter((task) => task.status === "pendente");
    if (state.view === "concluidas") tasks = tasks.filter((task) => task.status === "concluida");
    if (state.view === "atrasadas") tasks = tasks.filter((task) => task.atrasada);
    if (elements.statusFilter.value) tasks = tasks.filter((task) => task.status === elements.statusFilter.value);
    if (elements.priorityFilter.value) tasks = tasks.filter((task) => task.prioridade === elements.priorityFilter.value);
    if (elements.categoryFilter.value) tasks = tasks.filter((task) => task.categoria === elements.categoryFilter.value);
    if (elements.sortFilter.value === "prioridade") {
        const weight = { alta: 1, media: 2, baixa: 3 };
        tasks.sort((a, b) => weight[a.prioridade] - weight[b.prioridade]);
    } else if (elements.sortFilter.value === "data_limite") {
        tasks.sort((a, b) => (a.data_limite || "9999-12-31").localeCompare(b.data_limite || "9999-12-31"));
    } else {
        tasks.sort((a, b) => new Date(b.data_criacao) - new Date(a.data_criacao));
    }
    return tasks;
}

function taskTemplate(task) {
    const completed = task.status === "concluida";
    const archived = Boolean(task.arquivada);
    const category = task.categoria || "Sem categoria";
    const categoryInfo = categoryByName(task.categoria);
    const priority = ["baixa", "media", "alta"].includes(task.prioridade) ? task.prioridade : "media";
    const taskId = Number(task.id);
    const deadlineText = task.atrasada ? `Atrasada · ${formatDate(task.data_limite)}` : formatDate(task.data_limite);
    return `<article class="task-card ${completed ? "completed" : ""} ${task.atrasada ? "overdue" : ""} ${archived ? "archived" : ""}" data-task-id="${taskId}" tabindex="0" role="button" aria-label="Ver detalhes de ${escapeHTML(task.titulo)}">
        <div class="task-card-top"><span class="task-category" title="${escapeHTML(category)}">${escapeHTML(categoryInfo?.icone ? `${categoryInfo.icone} ${category}` : category)}</span>${archived ? '<span class="badge status-pending">Arquivada</span>' : ""}</div>
        <h3>${escapeHTML(task.titulo)}</h3><p class="task-description">${escapeHTML(task.descricao || "Nenhuma descrição adicionada.")}</p>
        <div class="task-meta ${task.atrasada ? "overdue-date" : ""}"><span aria-hidden="true">◷</span><time>${escapeHTML(archived ? `Arquivada em ${formatDetailDate(task.data_arquivamento)}` : deadlineText)}</time></div>
        <div class="task-footer"><div class="task-badges"><span class="badge priority-${priority}">${capitalize(priority)}</span>${completed ? '<span class="badge status-completed">Concluída</span>' : ""}</div><div class="task-actions">${archived ? `<button class="task-action" type="button" data-action="restore" data-id="${taskId}" aria-label="Restaurar tarefa" title="Restaurar">↶</button>` : `${completed ? "" : `<button class="task-action complete" type="button" data-action="complete" data-id="${taskId}" aria-label="Concluir tarefa" title="Concluir">✓</button>`}<button class="task-action" type="button" data-action="edit" data-id="${taskId}" aria-label="Editar tarefa" title="Editar">✎</button><button class="task-action" type="button" data-action="duplicate" data-id="${taskId}" aria-label="Duplicar tarefa" title="Duplicar">⧉</button><button class="task-action" type="button" data-action="archive" data-id="${taskId}" aria-label="Arquivar tarefa" title="Arquivar">▣</button>`}<button class="task-action delete" type="button" data-action="delete" data-id="${taskId}" aria-label="Excluir tarefa" title="Excluir">⌫</button></div></div>
    </article>`;
}

function emptyTemplate(hasFilter = false) {
    return `<div class="empty-state"><span class="empty-state-icon" aria-hidden="true">${hasFilter ? "⌕" : "✓"}</span><h3>${hasFilter ? "Nenhuma tarefa encontrada" : "Tudo organizado por aqui"}</h3><p>${hasFilter ? "Tente ajustar a busca ou limpar os filtros aplicados." : "Crie sua primeira tarefa para começar a organizar o dia."}</p><button class="btn ${hasFilter ? "btn-ghost" : "btn-primary"}" type="button" data-empty-action="${hasFilter ? "clear" : "new"}">${hasFilter ? "Limpar filtros" : "+ Nova tarefa"}</button></div>`;
}

function renderToday() {
    const groups = [
        ["Atrasadas", "!", state.hoje.atrasadas],
        ["Hoje", "◉", state.hoje.hoje],
        ["Concluídas hoje", "✓", state.hoje.concluidas],
    ];
    const count = groups.reduce((total, [, , tasks]) => total + tasks.filter(matchesSearch).length, 0);
    elements.resultCount.textContent = `${count} ${count === 1 ? "tarefa no seu dia" : "tarefas no seu dia"}`;
    if (!count) {
        elements.tasksGrid.innerHTML = emptyTemplate(Boolean(elements.searchInput.value));
        return;
    }
    elements.tasksGrid.innerHTML = groups.map(([label, icon, tasks]) => {
        const visible = tasks.filter(matchesSearch);
        if (!visible.length) return "";
        return `<section class="task-group"><h3 class="task-group-heading"><span aria-hidden="true">${icon}</span><strong>${label}</strong><small>${visible.length}</small></h3><div class="tasks-grid">${visible.map(taskTemplate).join("")}</div></section>`;
    }).join("");
}

function renderTasks() {
    if (state.view === "hoje") return renderToday();
    const tasks = visibleTasks();
    elements.resultCount.textContent = `${tasks.length} ${tasks.length === 1 ? "tarefa encontrada" : "tarefas encontradas"}`;
    if (!tasks.length) {
        const hasFilter = Boolean(elements.searchInput.value || elements.statusFilter.value || elements.priorityFilter.value || elements.categoryFilter.value || ["atrasadas", "pendentes", "concluidas", "arquivadas"].includes(state.view));
        elements.tasksGrid.innerHTML = emptyTemplate(hasFilter);
        return;
    }
    elements.tasksGrid.innerHTML = tasks.map(taskTemplate).join("");
}

function renderError(message) {
    elements.resultCount.textContent = "Falha ao carregar";
    elements.tasksGrid.innerHTML = `<div class="error-state"><span class="empty-state-icon" aria-hidden="true">!</span><h3>Não foi possível carregar as tarefas</h3><p>${escapeHTML(message)}</p><button class="btn btn-ghost" type="button" data-empty-action="retry">Tentar novamente</button></div>`;
}

async function loadBaseData(render = true) {
    if (render && !["calendario", "categorias", "dados"].includes(state.view)) renderLoading();
    try {
        const [tasks, categories] = await Promise.all([api("/tarefas"), api("/categorias")]);
        const pendingIds = new Set(state.pendingDeletes.keys());
        state.tarefas = tasks.filter((task) => !pendingIds.has(task.id));
        state.todas = [...state.tarefas];
        state.categorias = categories;
        updateCategoryOptions();
        renderSummary();
        renderDashboard();
        renderCategories();
        renderCurrentView();
        setConnection(true);
    } catch (error) {
        if (error.status === 401) return showAuth();
        setConnection(false);
        if (elements.tasksPanel.hidden) showToast(error.message, "error"); else renderError(error.message);
    }
}

async function loadToday() {
    renderLoading();
    try {
        state.hoje = await api("/tarefas/hoje");
        renderToday();
    } catch (error) {
        renderError(error.message);
    }
}

async function loadArchived() {
    renderLoading();
    try {
        const data = await api("/tarefas/arquivadas");
        const pendingIds = new Set(state.pendingDeletes.keys());
        state.arquivadas = data.tarefas.filter((task) => !pendingIds.has(task.id));
        if (data.removidas) showToast(`${data.removidas} tarefa(s) arquivada(s) há 30 dias foram removidas.`);
        renderTasks();
    } catch (error) {
        renderError(error.message);
    }
}

function showToast(message, type = "success") {
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    const text = document.createElement("span");
    text.textContent = message;
    toast.appendChild(text);
    elements.toastRegion.appendChild(toast);
    window.setTimeout(() => {
        toast.classList.add("leaving");
        window.setTimeout(() => toast.remove(), 200);
    }, 3400);
    return toast;
}

function showUndoToast(task) {
    const toast = document.createElement("div");
    toast.className = "toast undo";
    const text = document.createElement("span");
    text.textContent = "Tarefa excluída.";
    const button = document.createElement("button");
    button.className = "toast-action";
    button.type = "button";
    button.textContent = "Desfazer";
    button.addEventListener("click", () => undoDelete(task.id, toast));
    toast.append(text, button);
    elements.toastRegion.appendChild(toast);
    return toast;
}

function openNewTask() {
    if (!state.currentUser) return;
    state.editingId = null;
    elements.taskForm.reset();
    elements.taskPriority.value = "media";
    elements.modalEyebrow.textContent = "Nova tarefa";
    elements.modalTitle.textContent = "Adicionar tarefa";
    elements.saveTaskButton.textContent = "Criar tarefa";
    elements.taskModal.showModal();
    window.setTimeout(() => elements.taskTitle.focus(), 50);
}

async function openEditTask(id) {
    try {
        const task = await api(`/tarefas/${id}`);
        if (task.arquivada) throw new Error("Restaure a tarefa antes de editá-la.");
        state.editingId = id;
        elements.taskTitle.value = task.titulo;
        elements.taskDescription.value = task.descricao || "";
        elements.taskCategory.value = task.categoria || "";
        elements.taskPriority.value = task.prioridade;
        elements.taskDeadline.value = task.data_limite || "";
        elements.modalEyebrow.textContent = "Editar tarefa";
        elements.modalTitle.textContent = "Atualizar detalhes";
        elements.saveTaskButton.textContent = "Salvar alterações";
        elements.taskModal.showModal();
        window.setTimeout(() => elements.taskTitle.focus(), 50);
    } catch (error) {
        showToast(error.message, "error");
    }
}

function openTaskDetails(id) {
    const task = taskById(id);
    if (!task) return showToast("Tarefa não encontrada.", "error");
    state.detailsId = id;
    const completed = task.status === "concluida";
    const archived = Boolean(task.arquivada);
    const priority = ["baixa", "media", "alta"].includes(task.prioridade) ? task.prioridade : "media";
    elements.detailsTitle.textContent = task.titulo;
    elements.detailsCategory.textContent = task.categoria || "Sem categoria";
    elements.detailsPriority.className = `badge priority-${priority}`;
    elements.detailsPriority.textContent = capitalize(priority);
    elements.detailsStatus.className = `badge ${completed ? "status-completed" : "status-pending"}`;
    elements.detailsStatus.textContent = archived ? "Arquivada" : capitalize(task.status);
    elements.detailsDescription.textContent = task.descricao || "Nenhuma descrição adicionada.";
    elements.detailsCreatedAt.textContent = formatDetailDate(task.data_criacao);
    elements.detailsDeadline.textContent = formatDetailDate(task.data_limite);
    elements.detailsCompletedGroup.hidden = !completed;
    elements.detailsCompletedAt.textContent = completed ? formatDetailDate(task.data_conclusao) : "";
    elements.detailsArchivedGroup.hidden = !archived;
    elements.detailsArchivedAt.textContent = archived ? formatDetailDate(task.data_arquivamento) : "";
    [elements.detailsEdit, elements.detailsDuplicate, elements.detailsComplete, elements.detailsArchive].forEach((button) => { button.hidden = archived; });
    elements.detailsComplete.hidden = archived || completed;
    elements.detailsRestore.hidden = !archived;
    elements.detailsModal.showModal();
}

function closeTaskDetails() {
    state.detailsId = null;
    if (elements.detailsModal.open) elements.detailsModal.close();
}

async function saveTask(event) {
    event.preventDefault();
    const title = elements.taskTitle.value.trim();
    if (!title) {
        elements.taskTitle.focus();
        return showToast("Informe um título para a tarefa.", "error");
    }
    const payload = {
        titulo: title,
        descricao: elements.taskDescription.value.trim() || null,
        categoria: elements.taskCategory.value || null,
        prioridade: elements.taskPriority.value,
        data_limite: elements.taskDeadline.value || null,
    };
    const editing = state.editingId !== null;
    const originalLabel = elements.saveTaskButton.textContent;
    elements.saveTaskButton.disabled = true;
    elements.saveTaskButton.textContent = editing ? "Salvando..." : "Criando...";
    try {
        await api(editing ? `/tarefas/${state.editingId}` : "/tarefas", { method: editing ? "PUT" : "POST", body: JSON.stringify(payload) });
        elements.taskModal.close();
        state.editingId = null;
        showToast(editing ? "Tarefa atualizada com sucesso." : "Tarefa criada com sucesso.");
        await loadBaseData(false);
        if (state.view === "hoje") await loadToday();
    } catch (error) {
        showToast(error.message, "error");
    } finally {
        elements.saveTaskButton.disabled = false;
        elements.saveTaskButton.textContent = originalLabel;
    }
}

async function taskAction(id, action, message) {
    const key = `${action}:${id}`;
    if (!Number.isInteger(id) || state.pendingActions.has(key)) return;
    state.pendingActions.add(key);
    document.querySelectorAll(`[data-id="${id}"]`).forEach((button) => { button.disabled = true; });
    try {
        const method = action === "duplicar" ? "POST" : "PATCH";
        await api(`/tarefas/${id}/${action}`, { method });
        closeTaskDetails();
        showToast(message);
        await loadBaseData(false);
        if (state.view === "arquivadas") await loadArchived();
        if (state.view === "hoje") await loadToday();
    } catch (error) {
        showToast(error.message, "error");
    } finally {
        state.pendingActions.delete(key);
    }
}

function completeTask(id) { return taskAction(id, "concluir", "Tarefa marcada como concluída."); }
function duplicateTask(id) { return taskAction(id, "duplicar", "Tarefa duplicada como pendente."); }
function archiveTask(id) { return taskAction(id, "arquivar", "Tarefa arquivada por até 30 dias."); }
function restoreTask(id) { return taskAction(id, "restaurar", "Tarefa restaurada."); }

function removeTaskFromState(id) {
    state.tarefas = state.tarefas.filter((task) => task.id !== id);
    state.todas = state.todas.filter((task) => task.id !== id);
    Object.keys(state.hoje).forEach((key) => { state.hoje[key] = state.hoje[key].filter((task) => task.id !== id); });
    renderSummary();
    renderDashboard();
    renderCurrentView();
}

function stageDelete(id) {
    const task = taskById(id);
    if (!task || state.pendingDeletes.has(id)) return;
    if (task.arquivada) return confirmPermanentDelete(id);
    closeTaskDetails();
    removeTaskFromState(id);
    const toast = showUndoToast(task);
    const timer = window.setTimeout(() => commitDelete(id, toast), 5500);
    state.pendingDeletes.set(id, { task, timer });
}

async function undoDelete(id, toast) {
    const pending = state.pendingDeletes.get(id);
    if (!pending) return;
    window.clearTimeout(pending.timer);
    state.pendingDeletes.delete(id);
    state.tarefas.push(pending.task);
    state.todas.push(pending.task);
    toast.remove();
    renderSummary();
    renderDashboard();
    renderCurrentView();
    if (state.view === "hoje") await loadToday();
    showToast("Exclusão desfeita.");
}

async function commitDelete(id, toast) {
    const pending = state.pendingDeletes.get(id);
    if (!pending) return;
    state.pendingDeletes.delete(id);
    toast?.remove();
    try {
        await api(`/tarefas/${id}`, { method: "DELETE" });
    } catch (error) {
        state.tarefas.push(pending.task);
        state.todas.push(pending.task);
        renderSummary();
        renderDashboard();
        renderCurrentView();
        showToast(error.message, "error");
    }
}

function openConfirmation({ title, message, label = "Confirmar", handler }) {
    state.confirmHandler = handler;
    elements.confirmTitle.textContent = title;
    elements.confirmMessage.textContent = message;
    elements.confirmAction.textContent = label;
    elements.confirmModal.showModal();
}

async function runConfirmation() {
    if (!state.confirmHandler || elements.confirmAction.disabled) return;
    const handler = state.confirmHandler;
    const label = elements.confirmAction.textContent;
    elements.confirmAction.disabled = true;
    elements.confirmAction.textContent = "Processando...";
    try {
        await handler();
        elements.confirmModal.close();
        state.confirmHandler = null;
    } catch (error) {
        showToast(error.message, "error");
    } finally {
        elements.confirmAction.disabled = false;
        elements.confirmAction.textContent = label;
    }
}

function confirmPermanentDelete(id) {
    closeTaskDetails();
    openConfirmation({
        title: "Excluir definitivamente?",
        message: "Esta tarefa arquivada será removida de forma permanente.",
        label: "Excluir tarefa",
        handler: async () => {
            await api(`/tarefas/${id}`, { method: "DELETE" });
            state.arquivadas = state.arquivadas.filter((task) => task.id !== id);
            renderTasks();
            showToast("Tarefa excluída definitivamente.");
        },
    });
}

function openNewCategory() {
    state.editingCategoryId = null;
    elements.categoryForm.reset();
    elements.categoryColor.value = "#7c6df2";
    elements.categoryModalEyebrow.textContent = "Nova categoria";
    elements.categoryModalTitle.textContent = "Criar categoria";
    elements.saveCategoryButton.textContent = "Criar categoria";
    elements.categoryModal.showModal();
    window.setTimeout(() => elements.categoryName.focus(), 50);
}

function openEditCategory(id) {
    const category = state.categorias.find((item) => item.id === id);
    if (!category) return;
    state.editingCategoryId = id;
    elements.categoryName.value = category.nome;
    elements.categoryColor.value = category.cor;
    elements.categoryIcon.value = category.icone || "";
    elements.categoryModalEyebrow.textContent = "Editar categoria";
    elements.categoryModalTitle.textContent = "Atualizar categoria";
    elements.saveCategoryButton.textContent = "Salvar alterações";
    elements.categoryModal.showModal();
}

async function saveCategory(event) {
    event.preventDefault();
    const payload = { nome: elements.categoryName.value.trim(), cor: elements.categoryColor.value, icone: elements.categoryIcon.value.trim() || null };
    const editing = state.editingCategoryId !== null;
    elements.saveCategoryButton.disabled = true;
    try {
        await api(editing ? `/categorias/${state.editingCategoryId}` : "/categorias", { method: editing ? "PUT" : "POST", body: JSON.stringify(payload) });
        elements.categoryModal.close();
        state.editingCategoryId = null;
        showToast(editing ? "Categoria atualizada." : "Categoria criada.");
        await loadBaseData(false);
    } catch (error) {
        showToast(error.message, "error");
    } finally {
        elements.saveCategoryButton.disabled = false;
    }
}

function confirmDeleteCategory(id) {
    const category = state.categorias.find((item) => item.id === id);
    if (!category) return;
    openConfirmation({
        title: "Excluir categoria?",
        message: `A categoria ${category.nome} será removida, mas suas tarefas serão preservadas sem categoria.`,
        label: "Excluir categoria",
        handler: async () => {
            await api(`/categorias/${id}`, { method: "DELETE" });
            showToast("Categoria excluída sem remover tarefas.");
            await loadBaseData(false);
        },
    });
}

function renderCategories() {
    if (!state.categorias.length) {
        elements.categoriesGrid.innerHTML = '<div class="empty-state"><span class="empty-state-icon" aria-hidden="true">◇</span><h3>Nenhuma categoria criada</h3><p>Crie categorias para organizar suas tarefas.</p><button class="btn btn-primary" type="button" data-category-action="new">+ Nova categoria</button></div>';
        return;
    }
    elements.categoriesGrid.innerHTML = state.categorias.map((category) => {
        const count = state.todas.filter((task) => task.categoria === category.nome).length;
        return `<article class="category-card"><span class="category-swatch"><input type="color" value="${escapeHTML(category.cor)}" tabindex="-1" aria-label="Cor da categoria ${escapeHTML(category.nome)}" disabled></span><div><strong>${escapeHTML(category.icone ? `${category.icone} ${category.nome}` : category.nome)}</strong><small>${count} ${count === 1 ? "tarefa ativa" : "tarefas ativas"}</small></div><div class="category-actions"><button type="button" data-category-action="edit" data-id="${Number(category.id)}" aria-label="Editar ${escapeHTML(category.nome)}">✎</button><button class="delete" type="button" data-category-action="delete" data-id="${Number(category.id)}" aria-label="Excluir ${escapeHTML(category.nome)}">⌫</button></div></article>`;
    }).join("");
}

function dateKey(date) {
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function renderCalendar() {
    const month = state.calendarMonth;
    elements.calendarTitle.textContent = new Intl.DateTimeFormat("pt-BR", { month: "long", year: "numeric" }).format(month);
    const firstOffset = (new Date(month.getFullYear(), month.getMonth(), 1).getDay() + 6) % 7;
    const start = new Date(month.getFullYear(), month.getMonth(), 1 - firstOffset);
    const weekdays = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"].map((day) => `<div class="calendar-weekday" role="columnheader">${day}</div>`).join("");
    const cells = [];
    for (let index = 0; index < 42; index += 1) {
        const current = new Date(start);
        current.setDate(start.getDate() + index);
        const key = dateKey(current);
        const tasks = state.todas.filter((task) => task.data_limite === key && matchesSearch(task));
        const events = tasks.slice(0, 3).map((task) => `<span class="calendar-event ${task.prioridade === "alta" ? "high" : ""}" data-calendar-task="${Number(task.id)}">${escapeHTML(task.titulo)}</span>`).join("");
        const more = tasks.length > 3 ? `<span class="calendar-more">+${tasks.length - 3} tarefa(s)</span>` : "";
        const label = new Intl.DateTimeFormat("pt-BR", { dateStyle: "full" }).format(current);
        cells.push(`<button class="calendar-day ${current.getMonth() !== month.getMonth() ? "outside" : ""} ${key === localToday() ? "today" : ""} ${key === state.calendarSelected ? "selected" : ""}" type="button" data-calendar-date="${key}" aria-label="${escapeHTML(label)}, ${tasks.length} tarefa(s)" role="gridcell"><span class="calendar-day-number">${current.getDate()}</span>${events}${more}</button>`);
    }
    elements.calendarGrid.innerHTML = weekdays + cells.join("");
    renderSelectedDay();
}

function renderSelectedDay() {
    if (!state.calendarSelected) {
        elements.selectedDayTitle.textContent = "Selecione um dia";
        elements.selectedDayTasks.innerHTML = '<p class="muted-copy">Clique em um dia para ver suas tarefas.</p>';
        return;
    }
    elements.selectedDayTitle.textContent = formatDetailDate(state.calendarSelected);
    const tasks = state.todas.filter((task) => task.data_limite === state.calendarSelected && matchesSearch(task));
    elements.selectedDayTasks.innerHTML = tasks.length ? tasks.map(miniTaskTemplate).join("") : '<p class="muted-copy">Nenhuma tarefa com prazo neste dia.</p>';
}

function changeMonth(offset) {
    state.calendarMonth = new Date(state.calendarMonth.getFullYear(), state.calendarMonth.getMonth() + offset, 1);
    state.calendarSelected = null;
    renderCalendar();
}

function updateViewChrome(view) {
    state.view = view;
    const [eyebrow, title, list] = viewLabels[view];
    elements.pageEyebrow.textContent = eyebrow;
    elements.pageTitle.textContent = title;
    elements.listTitle.textContent = list;
    elements.navItems.forEach((item) => {
        const active = item.dataset.view === view;
        item.classList.toggle("active", active);
        if (active) item.setAttribute("aria-current", "page"); else item.removeAttribute("aria-current");
    });
    const taskView = ["dashboard", "hoje", "todas", "pendentes", "concluidas", "atrasadas", "arquivadas"].includes(view);
    elements.tasksPanel.hidden = !taskView;
    elements.summarySection.hidden = view !== "dashboard";
    elements.dashboardInsights.hidden = view !== "dashboard";
    elements.calendarPanel.hidden = view !== "calendario";
    elements.categoriesPanel.hidden = view !== "categorias";
    elements.dataPanel.hidden = view !== "dados";
    elements.filtersPanel.hidden = view === "hoje";
    elements.filterToggle.hidden = view === "hoje";
    elements.searchBox.hidden = ["categorias", "dados"].includes(view);
}

function renderCurrentView() {
    if (state.view === "calendario") renderCalendar();
    else if (state.view === "categorias") renderCategories();
    else if (state.view !== "dados") renderTasks();
}

async function setView(view) {
    updateViewChrome(view);
    elements.statusFilter.value = view === "pendentes" || view === "atrasadas" ? "pendente" : view === "concluidas" ? "concluida" : "";
    closeSidebar();
    if (view === "hoje") await loadToday();
    else if (view === "arquivadas") await loadArchived();
    else renderCurrentView();
}

function clearAllFilters() {
    elements.statusFilter.value = "";
    elements.priorityFilter.value = "";
    elements.categoryFilter.value = "";
    elements.sortFilter.value = "";
    elements.searchInput.value = "";
    updateViewChrome("todas");
    renderTasks();
}

function openSidebar() {
    elements.sidebar.classList.add("open");
    elements.sidebarOverlay.classList.add("show");
    elements.menuToggle.setAttribute("aria-expanded", "true");
}

function closeSidebar() {
    elements.sidebar.classList.remove("open");
    elements.sidebarOverlay.classList.remove("show");
    elements.menuToggle.setAttribute("aria-expanded", "false");
}

async function exportBackup() {
    if (state.pendingActions.has("backup")) return;
    state.pendingActions.add("backup");
    elements.exportBackupButton.disabled = true;
    try {
        const data = await api("/backup");
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = `taskflow-backup-${localToday()}.json`;
        link.click();
        URL.revokeObjectURL(link.href);
        showToast("Backup exportado com sucesso.");
    } catch (error) {
        showToast(error.message, "error");
    } finally {
        state.pendingActions.delete("backup");
        elements.exportBackupButton.disabled = false;
    }
}

async function prepareRestore(file) {
    elements.restoreBackupInput.value = "";
    if (!file) return;
    if (file.size > 2 * 1024 * 1024) return showToast("O backup excede o limite de 2 MB.", "error");
    let backup;
    try {
        backup = JSON.parse(await file.text());
    } catch (_error) {
        return showToast("O arquivo selecionado não contém JSON válido.", "error");
    }
    if (backup?.version !== 1) return showToast("Versão de backup não suportada.", "error");
    openConfirmation({
        title: "Restaurar este backup?",
        message: "Suas tarefas, categorias e preferências atuais serão substituídas. Esta ação não pode ser desfeita.",
        label: "Restaurar backup",
        handler: async () => {
            await api("/backup/restaurar", { method: "POST", body: JSON.stringify({ confirmar: true, backup }) });
            showToast("Backup restaurado com sucesso.");
            await loadBaseData(false);
        },
    });
}

function showOnboarding() {
    state.onboardingStep = 0;
    renderOnboarding();
    elements.onboardingModal.showModal();
}

function renderOnboarding() {
    const page = onboardingPages[state.onboardingStep];
    elements.onboardingIcon.textContent = page.icon;
    elements.onboardingTitle.textContent = page.title;
    elements.onboardingCopy.textContent = page.copy;
    elements.nextOnboarding.textContent = state.onboardingStep === onboardingPages.length - 1 ? "Começar" : "Próximo";
    elements.onboardingDots.replaceChildren(...onboardingPages.map((_, index) => {
        const dot = document.createElement("span");
        dot.className = `onboarding-dot ${index === state.onboardingStep ? "active" : ""}`;
        dot.setAttribute("aria-label", `Etapa ${index + 1} de ${onboardingPages.length}`);
        return dot;
    }));
}

async function finishOnboarding(createTask = false) {
    elements.skipOnboarding.disabled = true;
    elements.nextOnboarding.disabled = true;
    try {
        const data = await api("/preferencias", { method: "PATCH", body: JSON.stringify({ onboarding_concluido: true }) });
        setAuthenticatedUser(data.usuario);
        elements.onboardingModal.close();
        if (createTask) openNewTask();
    } catch (error) {
        showToast(error.message, "error");
    } finally {
        elements.skipOnboarding.disabled = false;
        elements.nextOnboarding.disabled = false;
    }
}

function isTypingTarget(target) {
    return target.matches("input, textarea, select") || target.isContentEditable;
}

function hasOpenDialog() {
    return Boolean(document.querySelector("dialog[open]"));
}

elements.newTaskButton.addEventListener("click", openNewTask);
elements.authForm.addEventListener("submit", submitAuth);
elements.authSwitch.addEventListener("click", () => setAuthMode(state.authMode === "login" ? "register" : "login"));
elements.logoutButton.addEventListener("click", logout);
elements.authModal.addEventListener("cancel", (event) => event.preventDefault());
elements.taskForm.addEventListener("submit", saveTask);
elements.categoryForm.addEventListener("submit", saveCategory);
elements.menuToggle.addEventListener("click", openSidebar);
elements.sidebarOverlay.addEventListener("click", closeSidebar);
elements.filterToggle.addEventListener("click", () => {
    const open = elements.filtersPanel.classList.toggle("open");
    elements.filterToggle.setAttribute("aria-expanded", String(open));
});
elements.navItems.forEach((item) => item.addEventListener("click", () => setView(item.dataset.view)));
[elements.statusFilter, elements.priorityFilter, elements.categoryFilter, elements.sortFilter].forEach((filter) => filter.addEventListener("change", () => renderTasks()));
let searchTimer;
elements.searchInput.addEventListener("input", () => {
    window.clearTimeout(searchTimer);
    searchTimer = window.setTimeout(renderCurrentView, 180);
});
elements.clearFilters.addEventListener("click", clearAllFilters);

elements.tasksGrid.addEventListener("click", (event) => {
    const actionButton = event.target.closest("[data-action]");
    const emptyButton = event.target.closest("[data-empty-action]");
    if (actionButton) {
        event.stopPropagation();
        const id = Number(actionButton.dataset.id);
        if (actionButton.dataset.action === "complete") completeTask(id);
        if (actionButton.dataset.action === "duplicate") duplicateTask(id);
        if (actionButton.dataset.action === "edit") openEditTask(id);
        if (actionButton.dataset.action === "delete") stageDelete(id);
        if (actionButton.dataset.action === "archive") archiveTask(id);
        if (actionButton.dataset.action === "restore") restoreTask(id);
        return;
    }
    const taskCard = event.target.closest(".task-card[data-task-id]");
    if (taskCard) openTaskDetails(Number(taskCard.dataset.taskId));
    if (emptyButton?.dataset.emptyAction === "new") openNewTask();
    if (emptyButton?.dataset.emptyAction === "clear") clearAllFilters();
    if (emptyButton?.dataset.emptyAction === "retry") loadBaseData();
});
elements.tasksGrid.addEventListener("keydown", (event) => {
    if (event.target.closest("[data-action]")) return;
    const card = event.target.closest(".task-card[data-task-id]");
    if (card && ["Enter", " "].includes(event.key)) {
        event.preventDefault();
        openTaskDetails(Number(card.dataset.taskId));
    }
});

[elements.importantTasks, elements.recentCompleted, elements.selectedDayTasks].forEach((container) => container.addEventListener("click", (event) => {
    const item = event.target.closest("[data-mini-task]");
    if (item) openTaskDetails(Number(item.dataset.miniTask));
}));

elements.detailsEdit.addEventListener("click", () => { const id = state.detailsId; closeTaskDetails(); openEditTask(id); });
elements.detailsDuplicate.addEventListener("click", () => duplicateTask(state.detailsId));
elements.detailsComplete.addEventListener("click", () => completeTask(state.detailsId));
elements.detailsArchive.addEventListener("click", () => archiveTask(state.detailsId));
elements.detailsRestore.addEventListener("click", () => restoreTask(state.detailsId));
elements.detailsDelete.addEventListener("click", () => stageDelete(state.detailsId));
[elements.closeDetailsX, elements.closeDetailsButton].forEach((button) => button.addEventListener("click", closeTaskDetails));

document.querySelectorAll("[data-close-modal]").forEach((button) => button.addEventListener("click", () => elements.taskModal.close()));
document.querySelectorAll("[data-close-category]").forEach((button) => button.addEventListener("click", () => elements.categoryModal.close()));
elements.newCategoryButton.addEventListener("click", openNewCategory);
elements.categoriesGrid.addEventListener("click", (event) => {
    const button = event.target.closest("[data-category-action]");
    if (!button) return;
    if (button.dataset.categoryAction === "new") openNewCategory();
    if (button.dataset.categoryAction === "edit") openEditCategory(Number(button.dataset.id));
    if (button.dataset.categoryAction === "delete") confirmDeleteCategory(Number(button.dataset.id));
});

elements.previousMonth.addEventListener("click", () => changeMonth(-1));
elements.nextMonth.addEventListener("click", () => changeMonth(1));
elements.calendarGrid.addEventListener("click", (event) => {
    const task = event.target.closest("[data-calendar-task]");
    if (task) {
        event.stopPropagation();
        openTaskDetails(Number(task.dataset.calendarTask));
        return;
    }
    const day = event.target.closest("[data-calendar-date]");
    if (day) {
        state.calendarSelected = day.dataset.calendarDate;
        renderCalendar();
    }
});

elements.cancelConfirm.addEventListener("click", () => { state.confirmHandler = null; elements.confirmModal.close(); });
elements.confirmAction.addEventListener("click", runConfirmation);
elements.exportBackupButton.addEventListener("click", exportBackup);
elements.restoreBackupInput.addEventListener("change", (event) => prepareRestore(event.target.files[0]));
elements.skipOnboarding.addEventListener("click", () => finishOnboarding(false));
elements.nextOnboarding.addEventListener("click", () => {
    if (state.onboardingStep < onboardingPages.length - 1) {
        state.onboardingStep += 1;
        renderOnboarding();
    } else finishOnboarding(true);
});
elements.onboardingModal.addEventListener("cancel", (event) => { event.preventDefault(); finishOnboarding(false); });

[elements.taskModal, elements.detailsModal, elements.categoryModal, elements.confirmModal].forEach((modal) => {
    modal.addEventListener("click", (event) => {
        if (event.target === modal) modal.close();
    });
});
elements.taskModal.addEventListener("close", () => { state.editingId = null; });
elements.detailsModal.addEventListener("close", () => { state.detailsId = null; });
elements.categoryModal.addEventListener("close", () => { state.editingCategoryId = null; });
elements.confirmModal.addEventListener("close", () => { state.confirmHandler = null; });

document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
        if (elements.authModal.open) return;
        if (elements.onboardingModal.open) {
            event.preventDefault();
            finishOnboarding(false);
            return;
        }
        const openModal = [elements.confirmModal, elements.categoryModal, elements.taskModal, elements.detailsModal]
            .find((modal) => modal.open);
        if (openModal) {
            event.preventDefault();
            openModal.close();
            return;
        }
    }
    if (!state.currentUser || isTypingTarget(event.target)) return;
    if (event.ctrlKey && event.key.toLocaleLowerCase() === "n") {
        event.preventDefault();
        if (!hasOpenDialog()) openNewTask();
    }
    if (event.key === "/" || (event.ctrlKey && event.key.toLocaleLowerCase() === "k")) {
        if (hasOpenDialog()) return;
        event.preventDefault();
        if (elements.searchBox.hidden) updateViewChrome("todas");
        elements.searchInput.focus();
    }
});

initializeSession();

