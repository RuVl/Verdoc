<script setup>
import CommonButton from "@/components/CommonButton.vue";
</script>

<template>
  <teleport to="body">
    <div class="wrapper">
      <div class="page-not-found">
        <div>
          <svg aria-label="A piece of paper torn in half" class="paper" height="300px" role="img" viewBox="0 0 300 300"
               width="300px">
            <g class="paper__outline" fill="none" stroke="hsl(0,10%,10%)" stroke-linecap="round" stroke-linejoin="round"
               stroke-width="8"
               transform="translate(61,4)">
              <g class="paper__top" transform="translate(0,25)">
                <polygon class="paper__shadow" fill="hsl(0,10%,70%)"
                         points="0 148,0 0,137 0,187 50,187 148,155 138,124 148,93 138,62 148,31 138"
                         stroke="none" transform="translate(-12,12)"/>
                <rect class="paper__tear-fill" fill="hsl(0,0%,100%)" height="23px" stroke="none" width="0" x="0"
                      y="137"/>
                <polygon class="paper__fill" fill="hsl(0,0%,100%)"
                         points="0 148,0 0,137 0,187 50,187 148,155 138,124 148,93 138,62 148,31 138"
                         stroke="none"/>
                <polygon class="paper__shadow" fill="hsl(0,10%,70%)" points="137 0,132 55,187 50,142 45" stroke="none"/>
                <polyline points="137 0,142 45,187 50"/>
                <polyline points="0 148,0 0,137 0,187 50,187 148"/>
                <g class="paper__lines" stroke="hsl(0,10%,70%)">
                  <polyline points="22 88,165 88"/>
                  <polyline points="22 110,165 110"/>
                  <polyline points="22 132,165 132"/>
                </g>
                <polyline class="paper__tear" points="0 148,31 138,62 148,93 138,124 148,155 138,187 148"
                          stroke-dasharray="198 198"
                          stroke-dashoffset="-198"/>
              </g>
              <g class="paper__bottom" transform="translate(0,25)">
                <polygon class="paper__shadow" fill="hsl(0,10%,70%)"
                         points="0 148,31 138,62 148,93 138,124 148,155 138,187 148,187 242,0 242"
                         stroke="none" transform="translate(-12,12)"/>
                <polygon class="paper__fill" fill="hsl(0,0%,100%)"
                         points="0 148,31 140,62 148,93 138,124 148,155 138,187 148,187 242,0 242"
                         stroke="none"/>
                <polyline points="187 148,187 242,0 242,0 148"/>
                <g class="paper__lines" stroke="hsl(0,10%,70%)">
                  <polyline points="22 154,165 154"/>
                  <polyline points="22 176,165 176"/>
                  <polyline points="22 198,94 198"/>
                </g>
                <polyline class="paper__tear" points="0 148,31 138,62 148,93 138,124 148,155 138,187 148"
                          stroke-dasharray="198 198"
                          stroke-dashoffset="-198"/>
              </g>
            </g>
          </svg>
        </div>
        <div>
          <h1>404</h1>
          <p>{{ $t('other.page_not_found') }}</p>
          <CommonButton class="btn-link" href="main">{{ $t('buttons.go_back_home') }}</CommonButton>
        </div>
      </div>
    </div>
  </teleport>
</template>

<style scoped>
.wrapper {
  display: flex;
  position: fixed;
  box-sizing: border-box;
  margin: 0;

  top: 0;
  left: 0;
  bottom: 0;
  right: 0;

  --hue: 223;
  --bg: hsl(var(--hue), 10%, 90%);
  --fg: hsl(var(--hue), 10%, 10%);
  --primary: hsl(var(--hue), 90%, 45%);
  --primary-down: hsl(var(--hue), 90%, 65%);
  --trans-dur: 0.3s;

  font: 500 1em / 1.5 'Montserrat', sans-serif;
  font-size: calc(16px + (24 - 16) * (100vw - 320px) / (2560 - 320));

  background-color: var(--bg);
  color: var(--fg);

  height: 100vh;
  transition: background-color var(--trans-dur), color var(--trans-dur);
}

.page-not-found {
  margin: auto;
  display: grid;
  grid-gap: 3em 1.5em;
  padding: 3em 1.5em;
  text-align: center;
}

h1 {
  font-size: 3em;
  line-height: 1;
  margin: 0 0 1.5rem;
}

p {
  margin: 0 0 2em;
}

.btn-link {
  padding: 0.75em 1.5em;
}

.paper {
  display: block;
  margin: auto;
  overflow: visible;
  width: 100%;
  max-width: 224px;
  height: auto;
}

.paper__fill {
  fill: hsl(0, 0%, 100%);
}

.paper__outline,
.paper__lines {
  transition: stroke var(--trans-dur);
}

.paper__outline {
  stroke: hsl(var(--hue), 10%, 10%);
}

.paper__lines {
  stroke: hsl(var(--hue), 10%, 70%);
}

.paper__shadow {
  fill: hsl(var(--hue), 10%, 70%);
  transition: fill var(--trans-dur);
}

.paper__top,
.paper__bottom,
.paper__tear,
.paper__tear-fill {
  animation: paperTop 1.25s cubic-bezier(0.77, 0, 0.18, 1);
}

.paper__top,
.paper__bottom {
  transform-origin: 0 148px;
  transition: transform var(--trans-dur) cubic-bezier(0.77, 0, 0.18, 1);
}

.paper__top {
  transform: translate(0, 8px);
}

.paper__bottom {
  animation-name: paperBottom;
  transform: translate(0, 42px);
}

.paper__tear,
.paper__tear-fill {
  animation-timing-function: cubic-bezier(0.32, 0, 0.67, 0);
}

.paper__tear {
  animation-name: paperTear;
  stroke-dashoffset: 0;
}

.paper__tear-fill {
  animation-name: paperTearFill;
}

.paper__outline:hover .paper__top,
.paper__outline:hover .paper__bottom {
  transform: translate(0, 25px);
}

/* Dark theme */
@media (prefers-color-scheme: dark) {
  .wrapper {
    --bg: hsl(var(--hue), 10%, 25%);
    --fg: hsl(var(--hue), 10%, 90%);
  }

  .paper__shadow:first-child {
    fill: hsl(var(--hue), 10%, 15%);
  }
}

/* Beyond mobile */
@media (min-width: 768px) {
  .page-not-found {
    grid-template-columns: 1fr 2fr;
    align-items: center;
    text-align: left;
  }

  .paper {
    max-width: 300px;
  }
}

/* Animations */
@keyframes paperTop {
  from,
  40% {
    animation-timing-function: cubic-bezier(0.32, 0, 0.67, 0);
    transform: translate(0, 25px) rotate(0);
    transform-origin: 61px 148px;
  }
  70% {
    animation-timing-function: cubic-bezier(0.33, 1, 0.67, 1.5);
    transform: translate(0, 25px) rotate(-5deg);
    transform-origin: 61px 148px;
  }
  to {
    transform: translate(0, 8px) rotate(0);
    transform-origin: 0 148px;
  }
}

@keyframes paperBottom {
  from,
  40% {
    animation-timing-function: cubic-bezier(0.32, 0, 0.67, 0);
    transform: translate(0, 25px) rotate(0);
    transform-origin: 61px 148px;
  }
  70% {
    animation-timing-function: cubic-bezier(0.33, 1, 0.67, 1.5);
    transform: translate(0, 25px) rotate(5deg);
    transform-origin: 61px 148px;
  }
  to {
    transform: translate(0, 42px) rotate(0);
    transform-origin: 0 148px;
  }
}

@keyframes paperTear {
  from,
  40% {
    stroke-dashoffset: -198;
  }
  70%,
  to {
    stroke-dashoffset: 0;
  }
}

@keyframes paperTearFill {
  from,
  40% {
    width: 187px;
  }
  70%,
  to {
    width: 0;
  }
}
</style>