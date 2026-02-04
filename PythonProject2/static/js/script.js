document.addEventListener("DOMContentLoaded", function () {
    const THEME_KEY = "ui-theme";
    const TRANSITION_KEY = "page-transition-direction";
    const routeOrder = [
        "/",
        "/theory",
        "/upload",
        "/profile",
        "/verify-email",
        "/admin/submissions",
        "/admin/users",
        "/admin/calendar",
        "/login",
        "/register"
    ];

    const pageContent = document.getElementById("page-content");
    const themeToggle = document.getElementById("themeToggle");
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const normalizePath = (urlLike) => {
        try {
            const url = new URL(urlLike, window.location.origin);
            return (url.pathname.replace(/\/+$/, "") || "/").toLowerCase();
        } catch (error) {
            return "/";
        }
    };

    const findRouteIndex = (path) => {
        for (let i = 0; i < routeOrder.length; i += 1) {
            const route = routeOrder[i];
            if (path === route || (route !== "/" && path.startsWith(route))) {
                return i;
            }
        }
        return routeOrder.length;
    };

    const updateThemeIcon = (theme) => {
        if (!themeToggle) {
            return;
        }
        const icon = themeToggle.querySelector("i");
        if (!icon) {
            return;
        }
        icon.classList.toggle("fa-moon", theme === "light");
        icon.classList.toggle("fa-sun", theme === "dark");
    };

    const setTheme = (theme) => {
        const safeTheme = theme === "dark" ? "dark" : "light";
        document.documentElement.setAttribute("data-theme", safeTheme);
        localStorage.setItem(THEME_KEY, safeTheme);
        updateThemeIcon(safeTheme);
    };

    const storedTheme = localStorage.getItem(THEME_KEY);
    setTheme(storedTheme === "dark" ? "dark" : "light");

    if (themeToggle) {
        themeToggle.addEventListener("click", () => {
            const current = document.documentElement.getAttribute("data-theme");
            setTheme(current === "dark" ? "light" : "dark");
        });
    }

    const enterDirection = sessionStorage.getItem(TRANSITION_KEY);
    sessionStorage.removeItem(TRANSITION_KEY);
    if (pageContent && enterDirection && !prefersReducedMotion) {
        pageContent.classList.add(enterDirection === "right" ? "is-entering-right" : "is-entering-left");
    }

    const alerts = document.querySelectorAll(".alert");
    alerts.forEach((alert) => {
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });

    const logoutLinks = document.querySelectorAll('a[href*="logout"]');
    logoutLinks.forEach((link) => {
        link.addEventListener("click", function (event) {
            if (!confirm("Вы уверены, что хотите выйти?")) {
                event.preventDefault();
            }
        });
    });

    document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
        anchor.addEventListener("click", function (event) {
            const targetId = this.getAttribute("href");
            const target = targetId ? document.querySelector(targetId) : null;
            if (!target) {
                return;
            }
            event.preventDefault();
            target.scrollIntoView({ behavior: "smooth" });
        });
    });

    document.querySelectorAll("a[href]").forEach((link) => {
        link.addEventListener("click", function (event) {
            if (event.defaultPrevented || prefersReducedMotion) {
                return;
            }
            if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) {
                return;
            }
            if (this.target && this.target !== "_self") {
                return;
            }
            const href = this.getAttribute("href");
            if (!href || href.startsWith("#") || href.startsWith("javascript:")) {
                return;
            }

            const targetPath = normalizePath(this.href);
            const currentPath = normalizePath(window.location.pathname);
            if (targetPath === currentPath) {
                return;
            }
            if (!this.href.startsWith(window.location.origin)) {
                return;
            }

            event.preventDefault();
            const currentIndex = findRouteIndex(currentPath);
            const targetIndex = findRouteIndex(targetPath);
            const direction = targetIndex >= currentIndex ? "left" : "right";
            sessionStorage.setItem(TRANSITION_KEY, direction);

            if (pageContent) {
                pageContent.classList.add(direction === "right" ? "is-exiting-right" : "is-exiting-left");
                setTimeout(() => {
                    window.location.assign(this.href);
                }, 280);
                return;
            }
            window.location.assign(this.href);
        });
    });

    const calendar = document.querySelector(".calendar");
    if (calendar) {
        const months = Array.from(calendar.querySelectorAll(".calendar-month"));
        const label = document.querySelector(".calendar-nav-label");
        const prevButton = document.querySelector(".calendar-nav-prev");
        const nextButton = document.querySelector(".calendar-nav-next");
        let activeIndex = 0;

        const updateCalendar = () => {
            months.forEach((month, index) => {
                month.classList.toggle("is-active", index === activeIndex);
            });
            if (label && months[activeIndex]) {
                label.textContent = months[activeIndex].dataset.monthLabel || "";
            }
            if (prevButton) {
                prevButton.disabled = activeIndex === 0;
            }
            if (nextButton) {
                nextButton.disabled = activeIndex === months.length - 1;
            }
        };

        if (months.length > 0) {
            updateCalendar();
            if (prevButton) {
                prevButton.addEventListener("click", () => {
                    if (activeIndex > 0) {
                        activeIndex -= 1;
                        updateCalendar();
                    }
                });
            }
            if (nextButton) {
                nextButton.addEventListener("click", () => {
                    if (activeIndex < months.length - 1) {
                        activeIndex += 1;
                        updateCalendar();
                    }
                });
            }
        }
    }

    if (prefersReducedMotion) {
        return;
    }

    const revealTargets = document.querySelectorAll(".card, .alert, .table-responsive");
    revealTargets.forEach((node, index) => {
        node.classList.add("reveal");
        node.style.transitionDelay = `${Math.min(index * 35, 240)}ms`;
    });

    const observer = new IntersectionObserver(
        (entries, obs) => {
            entries.forEach((entry) => {
                if (!entry.isIntersecting) {
                    return;
                }
                entry.target.classList.add("is-visible");
                obs.unobserve(entry.target);
            });
        },
        { threshold: 0.12, rootMargin: "0px 0px -6% 0px" }
    );

    revealTargets.forEach((node) => observer.observe(node));
});
