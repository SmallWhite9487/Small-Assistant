(function () {
  "use strict";

  const MODE_KEY = "sa.counter-quiz.mode";
  const COUNTERS = [
    { suffix: "つ", readings: ["ひとつ", "ふたつ", "みっつ", "よっつ", "いつつ", "むっつ", "ななつ", "やっつ", "ここのつ", "とお"] },
    { suffix: "個", readings: ["いっこ", "にこ", "さんこ", "よんこ", "ごこ", "ろっこ", "ななこ", "はっこ", "きゅうこ", "じゅっこ"] },
    { suffix: "本", readings: ["いっぽん", "にほん", "さんぼん", "よんほん", "ごほん", "ろっぽん", "ななほん", "はっぽん", "きゅうほん", "じゅっぽん"] },
    { suffix: "枚", readings: ["いちまい", "にまい", "さんまい", "よんまい", "ごまい", "ろくまい", "ななまい", "はちまい", "きゅうまい", "じゅうまい"] },
    { suffix: "冊", readings: ["いっさつ", "にさつ", "さんさつ", "よんさつ", "ごさつ", "ろくさつ", "ななさつ", "はっさつ", "きゅうさつ", "じゅっさつ"] },
    { suffix: "台", readings: ["いちだい", "にだい", "さんだい", "よんだい", "ごだい", "ろくだい", "ななだい", "はちだい", "きゅうだい", "じゅうだい"] },
    { suffix: "人", readings: ["ひとり", "ふたり", "さんにん", "よにん", "ごにん", "ろくにん", "ななにん", "はちにん", "きゅうにん", "じゅうにん"] },
    { suffix: "匹", readings: ["いっぴき", "にひき", "さんびき", "よんひき", "ごひき", "ろっぴき", "ななひき", "はっぴき", "きゅうひき", "じゅっぴき"] },
    { suffix: "羽", readings: ["いちわ", "にわ", "さんわ", "よんわ", "ごわ", "ろくわ", "ななわ", "はちわ", "きゅうわ", "じゅうわ"] },
    { suffix: "頭", readings: ["いっとう", "にとう", "さんとう", "よんとう", "ごとう", "ろくとう", "ななとう", "はっとう", "きゅうとう", "じゅっとう"] },
    { suffix: "杯", readings: ["いっぱい", "にはい", "さんばい", "よんはい", "ごはい", "ろっぱい", "ななはい", "はっぱい", "きゅうはい", "じゅっぱい"] },
    { suffix: "回", readings: ["いっかい", "にかい", "さんかい", "よんかい", "ごかい", "ろっかい", "ななかい", "はっかい", "きゅうかい", "じゅっかい"] },
    { suffix: "階", readings: ["いっかい", "にかい", "さんがい", "よんかい", "ごかい", "ろっかい", "ななかい", "はっかい", "きゅうかい", "じゅっかい"] },
    { suffix: "着", readings: ["いっちゃく", "にちゃく", "さんちゃく", "よんちゃく", "ごちゃく", "ろくちゃく", "ななちゃく", "はっちゃく", "きゅうちゃく", "じゅっちゃく"] },
    { suffix: "番", readings: ["いちばん", "にばん", "さんばん", "よんばん", "ごばん", "ろくばん", "ななばん", "はちばん", "きゅうばん", "じゅうばん"] },
  ];
  const SPECIAL_QUESTIONS = [
    { prompt: "何個", answer: "なんこ", distractors: ["いっこ", "さんこ", "いくつ"] },
    { prompt: "幾つ", answer: "いくつ", distractors: ["ひとつ", "よっつ", "なんこ"] },
  ];
  const state = {
    mode: "choices",
    started: false,
    question: null,
    options: [],
    answered: false,
    lastKey: "",
    total: 0,
    correct: 0,
  };
  const $ = (id) => document.getElementById(id);

  try {
    const savedMode = localStorage.getItem(MODE_KEY);
    if (savedMode === "choices" || savedMode === "typing") state.mode = savedMode;
  } catch (error) { /* storage may be blocked */ }

  function shuffle(items) {
    for (let index = items.length - 1; index > 0; index -= 1) {
      const swap = Math.floor(Math.random() * (index + 1));
      [items[index], items[swap]] = [items[swap], items[index]];
    }
    return items;
  }

  function makeQuestionPool() {
    const questions = [];
    for (const counter of COUNTERS) {
      counter.readings.forEach((answer, index) => {
        questions.push({
          key: counter.suffix + ":" + index,
          prompt: counter.suffix === "つ" && index === 9
            ? "十"
            : String(index + 1) + counter.suffix,
          number: counter.suffix === "つ" && index === 9 ? null : String(index + 1),
          suffix: counter.suffix,
          answer,
          distractors: counter.readings.filter((_, otherIndex) => otherIndex !== index),
        });
      });
    }
    for (const question of SPECIAL_QUESTIONS) {
      questions.push({
        ...question,
        key: "special:" + question.prompt,
      });
    }
    return questions;
  }

  function nextQuestion() {
    const pool = makeQuestionPool().filter((question) => question.key !== state.lastKey);
    state.question = pool[Math.floor(Math.random() * pool.length)];
    state.lastKey = state.question.key;
    state.answered = false;
    state.options = [];
    renderQuestion();
  }

  function setMode(mode) {
    state.mode = mode;
    try {
      localStorage.setItem(MODE_KEY, mode);
    } catch (error) { /* storage may be blocked */ }
    for (const button of $("counter-answer-mode").querySelectorAll("[data-mode]")) {
      button.classList.toggle("active", button.dataset.mode === mode);
    }
    if (state.started && state.question) {
      state.answered = false;
      renderQuestion();
    }
  }

  function updateScore() {
    $("counter-quiz-stats").textContent = SA.t("counter_quiz.score", {
      correct: state.correct,
      total: state.total,
    });
  }

  function renderQuestion() {
    const question = state.question;
    if (!question) return;
    $("counter-question").hidden = false;
    $("counter-quiz-start").hidden = true;
    const prompt = $("counter-prompt");
    prompt.replaceChildren();
    if (question.number) {
      const number = document.createElement("span");
      number.textContent = question.number;
      const suffix = document.createElement("span");
      suffix.textContent = question.suffix;
      prompt.append(number, suffix);
    } else {
      prompt.textContent = question.prompt;
    }
    $("counter-feedback").textContent = "";
    $("counter-feedback").className = "quiz-feedback";
    $("counter-next").hidden = true;
    $("counter-options").replaceChildren();
    $("counter-options").hidden = state.mode !== "choices";
    $("counter-input-row").hidden = state.mode !== "typing";
    $("counter-entry").value = "";
    $("counter-entry").disabled = false;
    $("counter-check").disabled = false;

    if (state.mode === "choices") {
      const values = [question.answer];
      const candidates = shuffle(question.distractors.slice());
      for (const candidate of candidates) {
        if (!values.includes(candidate)) values.push(candidate);
        if (values.length === 4) break;
      }
      state.options = shuffle(values);
      state.options.forEach((value, index) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "option";
        button.dataset.answer = value;
        const key = document.createElement("span");
        key.className = "key";
        key.textContent = String(index + 1);
        const label = document.createElement("span");
        label.textContent = value;
        button.append(key, label);
        $("counter-options").append(button);
      });
    } else {
      window.setTimeout(() => $("counter-entry").focus(), 0);
    }
  }

  function normalizeAnswer(value) {
    const normalized = value.normalize("NFKC").replace(/\s+/g, "");
    return Array.from(normalized, (character) => {
      const code = character.codePointAt(0);
      return code >= 0x30a1 && code <= 0x30f6
        ? String.fromCodePoint(code - 0x60)
        : character;
    }).join("");
  }

  function submitAnswer(value) {
    if (!state.question || state.answered) return;
    const normalized = normalizeAnswer(value);
    const correct = normalized === state.question.answer
      || (state.mode === "typing" && normalized === normalizeAnswer(state.question.prompt));
    state.answered = true;
    state.total += 1;
    if (correct) state.correct += 1;
    updateScore();
    $("counter-feedback").textContent = correct
      ? SA.t("counter_quiz.correct", { answer: state.question.answer })
      : SA.t("counter_quiz.incorrect", { answer: state.question.answer });
    $("counter-feedback").className = "quiz-feedback " + (correct ? "ok" : "bad");
    $("counter-next").hidden = false;
    for (const button of $("counter-options").querySelectorAll(".option")) {
      button.disabled = true;
      if (button.dataset.answer === state.question.answer) button.classList.add("correct");
      else if (normalizeAnswer(value) === button.dataset.answer) button.classList.add("wrong");
    }
    $("counter-entry").disabled = true;
    $("counter-check").disabled = true;
  }

  function start() {
    state.started = true;
    state.total = 0;
    state.correct = 0;
    state.lastKey = "";
    $("counter-quiz-stop").hidden = false;
    nextQuestion();
    $("counter-quiz-stats").textContent = SA.t("counter_quiz.score", {
      correct: state.correct,
      total: state.total,
    });
  }

  function stop() {
    state.started = false;
    state.question = null;
    $("counter-question").hidden = true;
    $("counter-quiz-start").hidden = false;
    $("counter-quiz-stop").hidden = true;
  }

  $("counter-answer-mode").addEventListener("click", (event) => {
    const button = event.target.closest("[data-mode]");
    if (!button || button.dataset.mode === state.mode) return;
    setMode(button.dataset.mode);
  });
  $("counter-quiz-start-button").addEventListener("click", start);
  $("counter-quiz-stop").addEventListener("click", stop);
  $("counter-next").addEventListener("click", nextQuestion);
  $("counter-options").addEventListener("click", (event) => {
    const button = event.target.closest("[data-answer]");
    if (button) submitAnswer(button.dataset.answer);
  });
  $("counter-check").addEventListener("click", () => submitAnswer($("counter-entry").value));
  $("counter-entry").addEventListener("keydown", (event) => {
    if (event.key === "Enter") submitAnswer($("counter-entry").value);
  });
  document.addEventListener("keydown", (event) => {
    if (!state.started || state.mode !== "choices" || state.answered) return;
    if (document.querySelector("dialog[open]") || event.metaKey || event.ctrlKey || event.altKey) return;
    if (!/^[1-4]$/.test(event.key)) return;
    const button = $("counter-options").querySelectorAll(".option")[Number(event.key) - 1];
    if (button) button.click();
  });

  setMode(state.mode);
  SA.ready.then(() => {
    updateScore();
  });
})();
