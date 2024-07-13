<script setup>
import {useRouter} from "vue-router";

const router = useRouter();
const route_chain = [];

for (let route = router.currentRoute.value; ; route = router.resolve({name: route.meta['parent']})) {
  route_chain.unshift(route);
  if (!router.hasRoute(route.meta['parent'])) break;
}
</script>

<template>
  <nav v-if="route_chain" class="path-nav">
    <span v-for="route in route_chain">
      <router-link :to="route">{{ route.meta.title }}</router-link>
    </span>
  </nav>
</template>

<style scoped lang="scss">
.path-nav {
  font-size: 12px;
  color: var(--second-color-text);

  & > span:not(:last-child)::after {
    margin: 0 10px;
    content: '/';
  }

  a {
    text-decoration: none;
    color: inherit;

    &:hover {
      opacity: .7;
    }
  }
}
</style>