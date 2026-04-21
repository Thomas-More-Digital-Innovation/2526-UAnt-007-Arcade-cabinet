<template>
  <q-card>
    <q-card-section class="flex items-center justify-between">
      <div class="text-h6">{{ title }}</div>
      <q-btn color="primary" icon="science" label="Test" unelevated @click="openGame" />
    </q-card-section>
    <q-card-section class="flex gap-2 justify-end">
      <q-btn color="primary" icon="edit" unelevated :ripple="false" label="Edit" @click="onEdit" />
      <q-btn
        color="negative"
        icon="delete"
        unelevated
        :ripple="false"
        label="Remove"
        @click="onRemove"
      />
    </q-card-section>

    <!-- Fullscreen game overlay -->
    <q-dialog v-model="gameOpen" maximized transition-show="fade" transition-hide="fade">
      <div class="game-fullscreen-container" @click.self="gameOpen = false">
        <q-btn
          class="game-close-btn"
          icon="close"
          color="white"
          text-color="dark"
          round
          unelevated
          @click="gameOpen = false"
        />

        <!-- Viewport clipping shell -->
        <div class="game-viewport-shell">
          <div
            class="game-scaler"
            :style="{
              width: nativeW + 'px',
              height: nativeH + 'px',
              transform: `scale(${scaleX}, ${scaleY})`,
              transformOrigin: 'top left',
            }"
          >
            <iframe
              v-if="gameOpen"
              ref="iframeRef"
              :src="`${api.defaults.baseURL}/games/${props.id}/test?api_key=${apiKey}`"
              class="game-iframe"
              :style="{ width: nativeW + 'px', height: nativeH + 'px' }"
              frameborder="0"
              scrolling="no"
              allowfullscreen
              allow="autoplay; fullscreen"
              @load="onIframeLoad"
            />
          </div>
        </div>
      </div>
    </q-dialog>
  </q-card>
</template>

<script setup lang="ts">
import { ref, watch, onUnmounted } from 'vue';
import { api } from 'boot/axios';

const props = defineProps<{
  title: string;
  id: string;
  modal: { name: string };
}>();
const emit = defineEmits(['edit', 'update:modal', 'delete']);

// ── State ─────────────────────────────────────────────────────────────────────
const gameOpen = ref(false);
const iframeRef = ref<HTMLIFrameElement | null>(null);

const apiKey = import.meta.env.VITE_API_KEY;

/** Native (unscaled) dimensions of the game page */
const nativeW = ref(1280);
const nativeH = ref(720);

/** Scale factors applied via CSS transform */
const scaleX = ref(1);
const scaleY = ref(1);

// ── Scale computation ─────────────────────────────────────────────────────────
function computeScale() {
  scaleX.value = window.innerWidth / nativeW.value;
  scaleY.value = window.innerHeight / nativeH.value;
}

function onIframeLoad() {
  try {
    const doc = iframeRef.value?.contentDocument;
    if (doc) {
      const w = doc.documentElement.scrollWidth || doc.body?.scrollWidth;
      const h = doc.documentElement.scrollHeight || doc.body?.scrollHeight;
      if (w > 0) nativeW.value = w;
      if (h > 0) nativeH.value = h;
    }
  } catch {
    // cross-origin — keep defaults
  }
  computeScale();
}

function onResize() {
  computeScale();
}

window.addEventListener('resize', onResize);
onUnmounted(() => window.removeEventListener('resize', onResize));

// Reset & recompute whenever the dialog opens
watch(gameOpen, (open) => {
  if (open) {
    nativeW.value = 1280;
    nativeH.value = 720;
    computeScale();
  }
});

// ── Card actions ──────────────────────────────────────────────────────────────
function openGame() {
  gameOpen.value = true;
}

function onEdit() {
  emit('edit', props.title);
}

function onRemove() {
  emit('delete', props.title);
}
</script>

<style scoped>
.game-fullscreen-container {
  position: relative;
  width: 100vw;
  height: 100vh;
  background: #000;
  overflow: hidden;
  display: flex;
  align-items: flex-start;
  justify-content: flex-start;
}

.game-close-btn {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 10;
  opacity: 0.85;
  transition: opacity 0.2s;
}

.game-close-btn:hover {
  opacity: 1;
}

/* Clips anything that overflows after scaling */
.game-viewport-shell {
  position: absolute;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  overflow: hidden;
}

/* The element that is scaled — its top-left corner sits at the shell's origin */
.game-scaler {
  position: absolute;
  top: 0;
  left: 0;
}

.game-iframe {
  display: block;
  border: none;
}
</style>
