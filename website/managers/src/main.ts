import { createApp } from "vue";
import { createPinia } from "pinia";

import App from "./App.vue";
import router from "./router";
import { useAuthStore } from "./stores/auth";
import "./charts/setup";
import "./styles/tailwind.css";
import "./styles/index.less";


const app = createApp(App);
const pinia = createPinia();

app.use(pinia);
app.use(router);

const authStore = useAuthStore(pinia);
if (typeof window !== "undefined") {
  window.addEventListener("classrobot-admin-unauthorized", () => {
    authStore.logout();
  });
}

app.mount("#app");
