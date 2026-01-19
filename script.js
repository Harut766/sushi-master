let fish = 0;

const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

const roll = document.getElementById("roll");
const fishEl = document.getElementById("fish");

roll.addEventListener("click", () => {
  fish += 1;
  fishEl.textContent = fish;

  // анимация ролла
  roll.style.transform = "scale(1.2)";
  setTimeout(() => {
    roll.style.transform = "scale(1)";
  }, 100);

  // вибрация (работает только в Telegram)
  if (tg.HapticFeedback) {
    tg.HapticFeedback.impactOccurred("light");
  }

  // всплывающий +1 🐟
  showPlusOne();
});

function showPlusOne() {
  const plus = document.createElement("div");
  plus.textContent = "+1 🐟";
  plus.className = "plus-one";

  document.body.appendChild(plus);

  setTimeout(() => {
    plus.remove();
  }, 800);
}
