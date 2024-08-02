<script setup>
const is_active = defineModel('is_active', {type: Boolean, default: false});
</script>

<template>
  <svg xmlns="http://www.w3.org/2000/svg" :class="{active: is_active}" @click="is_active=!is_active" viewbox="0 0 40 20">
    <path class="top-line" d="M10,10 L40,10 Z"/>
    <path class="middle-line" d="M10,20 L40,20 Z"/>
    <path class="bottom-line" d="M10,30 L40,30 Z"/>
  </svg>
</template>

<style scoped lang="scss">
svg {
  display: block;
  width: 50px;
  height: 40px;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 3;

  > path {
    transform-box: fill-box;
    transform-origin: center;
  }
}

svg.active {
  .top-line {
    animation: down-rotate 0.6s ease-out both;
  }
  .bottom-line {
    animation: up-rotate 0.6s ease-out both;
  }
  .middle-line {
    animation: hide 0.6s ease-out forwards;
  }
}

@keyframes up-rotate {
  0% {
    animation-timing-function: cubic-bezier(0.16, -0.88, 0.97, 0.53);
    transform: translateY(0px);
  }
  30% {
    transform-origin: center;
    animation-timing-function: cubic-bezier(0.34, 1.56, 0.64, 1);
    transform: translateY(-10px);
  }
  100% {
    transform-origin: center;
    transform: translateY(-10px) rotate(45deg) scale(0.9);
  }
}

@keyframes down-rotate {
  0% {
    animation-timing-function: cubic-bezier(0.16, -0.88, 0.97, 0.53);
    transform: translateY(0px);
  }
  30% {
    transform-origin: center;
    animation-timing-function: cubic-bezier(0.34, 1.56, 0.64, 1);
    transform: translateY(10px);
  }
  100% {
    transform-origin: center;
    transform: translateY(10px) rotate(-45deg) scale(0.9);
  }
}

@keyframes hide {
  29% {
    opacity: 1;
  }
  30% {
    opacity: 0;
  }
  100% {
    opacity: 0;
  }
}
</style>