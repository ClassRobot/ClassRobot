const BotManager = {
    el: "#app",
    data: {
        units: ["KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB", "BB", "NB", "DB", "CB"],
        display_card: {
            bot: true,
            login: true
        },
        bots: {},
        bot_files: [],
        selectRobot: {
            user_id: null
        },
        qrcode: null,
        wss_status: false,
        config: {
            wss_url: `ws://${location.host}${location.pathname}/wss`,
        },
        logger: {
            date_list: [],
            date: "",
            text: "",
            length: 500
        },
        login_form: {
            username: "",
            password: "",
            display: false
        },
        system_state: {
            cpu_percent: 0,
            disk: {
                total: 0,
                used: 0,
                free: 0,
                percent: 0
            },
            memory: {
                total: 0,
                used: 0,
                free: 0,
                percent: 0
            }
        }
    },
    methods: {
        // 针对websocket的消息处理
        async MessageEvent(message) {
            if (message.type in this.EventList) {
                // console.log(message);
                await this.EventList[message.type](message);
            }
        },
        async send(api, data) {
            while (this.websocket.readyState != 1) await this.sleep(1);
            await this.websocket.send(JSON.stringify({ api, data }));
        },
        async ping() {
            await this.connect();
            while (true) {
                if (this.websocket.readyState == 3) await this.connect();
                else if (this.websocket.readyState != 1 && this.wss_status) this.wss_status = false;
                await this.sleep(1);
            };
        },
        async connect() {
            this.websocket = new WebSocket(this.config.wss_url);
            this.websocket.addEventListener("open", () => this.wss_status = true);
            this.websocket.addEventListener('message', async message => await this.MessageEvent(JSON.parse(message.data)));
            this.websocket.addEventListener("close", () => this.wss_status = false);
        },
        /**睡眠
         * 
         * @param {Number} t 
         */
        async sleep(t) {
            return new Promise(resolve => setTimeout(resolve, t));
        },
        // 页面方法
        checkBot(user_id) {
            return user_id in this.bots;
        },
        updateList() {
            this.bots = {};
            this.bot_files = [];
            this.send("update_list");
        },
        loginBot(user_id, password) {
            if (user_id && !isNaN(parseInt(user_id))) {
                this.send("login_bot", { user_id, password });
            } else {
                alert("账号输入有误！！！")
            }
        },
        botStop(user_id) {
            this.send("bot_stop", { user_id })
        },
        robotDetails(user_id) {
            this.selectRobot.user_id = user_id;
            if (user_id) this.send("robot_etails", { user_id });
        },
        botLogger(user_id, date, refresh) {
            if ((this.logger.date != date || refresh) && user_id) {
                this.send("bot_logger", { user_id, date });
            };
        },
        loggerColor(message) {
            return message.replace(
                /\[(WARNING)\]/, "[<font color='#e7f533'>$1</font>]"
            ).replace(
                /\[(SUCCESS)\]/, "[<font color='#0dbc5c'>$1</font>]"
            ).replace(
                /\[(DEBUG)\]/, "[<font color='#3b8eca'>$1</font>]"
            ).replace(
                /\[(ERROR)\]/, "[<font color='red'>$1</font>]"
            ).replace(
                /(OneBot V\d+ \d+)/, "<font color='#c965c9'>$1</font>"
            ).replace(
                /((https?:\/\/)([\w=?./%&;-]+))/g, '<a target="_blank" rel="nofollow" href="$1" title="$1">$1</a>'
            );
        },
        megabyte(size) {
            // console.log(size);
            size /= 1024;
            for (let unit of this.units) {
                if (size >= 1024) size /= 1024;
                else return `${parseInt(size)}${unit}`;
            }
        }
    },
    computed: {
        botLoggerText() {
            if (this.logger.text) {
                try {
                    let text_list = this.logger.text.split("\n");
                    return this.$refs.botLogger.innerHTML =
                        text_list.slice(
                            text_list.length - this.logger.length - 1, text_list.length
                        ).map(e => this.loggerColor(e)).join("<br>");
                } finally {
                    this.$refs.botLogger.scrollTop = this.$refs.botLogger.scrollHeight;
                };
            };
        },
        cpu_percent() { return this.system_state.cpu_percent },
        disk() {
            return {
                total: this.megabyte(this.system_state.disk.total),
                used: this.megabyte(this.system_state.disk.used),
                free: this.megabyte(this.system_state.disk.free),
                percent: this.system_state.disk.percent + "%",
            }
        },
        memory() {
            return {
                total: this.megabyte(this.system_state.memory.total),
                used: this.megabyte(this.system_state.memory.used),
                free: this.megabyte(this.system_state.memory.free),
                percent: this.system_state.memory.percent + "%",
            }
        },
    },
    async created() {
        this.EventList = {
            ClientConnect: data => data.data.forEach(bot => {
                this.$set(this.bots, bot.user_id, bot);
                if (this.qrcode != null) {
                    if (this.qrcode.user_id == bot.user_id) {
                        this.qrcode = null;
                    };
                };
            }),
            LoginQrcode: data => this.qrcode = data,
            BotConnect: data => {
                this.EventList.ClientConnect(data)
            },
            BotDisconnect: data => data.data.forEach(bot => this.$delete(this.bots, bot.user_id)),
            BotFiles: data => this.bot_files = data.data,
            BotLogger: async data => {
                if (this.logger.text != data.text) {
                    this.logger.date_list = data.date_list.reverse();
                    this.logger.text = data.text;
                    this.logger.date = data.date;
                };
            },
            SystemLogger: data => {
                let p = document.createElement("div");
                p.innerHTML = this.loggerColor(data.data.replace(/(\d+-\d+ \d+:\d+:\d+) \[(\w+)\] (\w+)/g,
                    "<font color='#0dbc5c'>$1</font> [$2] <font color='#1b89cd'>$3</font>"
                )).replace(/\n/g, "<br>");
                this.$refs.systemLogger.appendChild(p);
                this.$refs.systemLogger.scrollTop = this.$refs.systemLogger.scrollHeight;
            },
            SystemState: data => {
                this.system_state.cpu_percent = data.cpu_percent;
                this.system_state.disk.total = data.disk.total;
                this.system_state.disk.used = data.disk.used;
                this.system_state.disk.free = data.disk.free;
                this.system_state.disk.percent = data.disk.percent;
                this.system_state.memory.total = data.memory.total;
                this.system_state.memory.used = data.memory.used;
                this.system_state.memory.free = data.memory.free;
                this.system_state.memory.percent = data.memory.percent;
                // console.log(this.system_state);
            }
        };
        await this.ping()
    }
};
const app = new Vue(BotManager)