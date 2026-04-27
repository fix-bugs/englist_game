document.querySelectorAll("[data-speech-target]").forEach((button) => {
    button.addEventListener("click", () => {
        const targetId = button.getAttribute("data-speech-target");
        const target = document.getElementById(targetId);
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

        if (!SpeechRecognition) {
            window.alert("当前浏览器不支持语音录入，请改用键盘输入。");
            return;
        }

        const recognition = new SpeechRecognition();
        recognition.lang = "en-US";
        recognition.interimResults = false;
        recognition.maxAlternatives = 1;

        button.disabled = true;
        button.textContent = "正在聆听...";

        recognition.onresult = (event) => {
            target.value = event.results[0][0].transcript;
        };

        recognition.onerror = () => {
            window.alert("语音识别失败，请再试一次。");
        };

        recognition.onend = () => {
            button.disabled = false;
            button.textContent = "语音录入";
        };

        recognition.start();
    });
});
