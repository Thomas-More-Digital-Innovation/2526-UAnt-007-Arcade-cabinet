<template>
  <q-page class="container mx-auto px-5 md:px-0">
    <div class="flex justify-between mt-10">
      <q-btn unelevated icon="rocket_launch" color="primary" label="Update Pi" :ripple="false" @click="updatePi" />
      <q-btn color="green" icon="add" label="Add Game" unelevated :ripple="false" @click="confirm = true" />
    </div>

    <!-- Game skeleton loaders -->
    <div v-if="isLoading" class="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
      <q-card v-for="i in 3" :key="`skeleton-${i}`">
        <q-card-section class="flex items-center justify-between">
          <q-skeleton type="text" width="50%" class="text-h6" animation="fade" />
          <q-skeleton type="QBtn" width="80px" height="36px" animation="fade" />
        </q-card-section>
        <q-card-section class="flex gap-2 justify-end">
          <q-skeleton type="QBtn" width="80px" height="36px" animation="fade" />
          <q-skeleton type="QBtn" width="100px" height="36px" animation="fade" />
        </q-card-section>
      </q-card>
    </div>

    <!-- Game cards -->
    <div v-else class="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
      <game-card v-for="game in data" :key="game.id" :title="game.name" :modal="modalGame" :id="game.id"
        :is-active="game.is_active" @edit="onEditGame(game)" @delete="deleteGame(game)"
        @update:active="toggleActive(game, $event)" />
    </div>

    <!-- Add/Edit game dialog -->
    <q-dialog v-model="confirm" @hide="resetModal">
      <q-card class="w-120">
        <q-card-section class="row items-center">
          <div class="text-h6">{{ isEditMode ? 'Edit Game' : 'New Game' }}</div>
          <q-space />
          <q-btn icon="close" unelevated v-close-popup />
        </q-card-section>
        <q-card-section class="flex flex-col gap-4">
          <q-input v-model="modalGame.name" type="text" label="Game Name" />
          <q-input v-model="modalGame.description" type="textarea" label="Game Description (Story/Explanation)" autogrow
            hint="This will be shown on the start screen before the game launches." />
          <!-- Show uploader only in add mode -->
          <q-uploader v-if="!isEditMode" ref="uploaderRef" accept=".zip" label="Upload ZIP folder" field-name="file"
            :auto-upload="false" :hide-upload-btn="true" />
        </q-card-section>
        <q-card-section v-if="isEditMode" class="scroll max-h-[50vh]">
          <div class="text-subtitle2 q-mb-md">Analyzed ZIP assets</div>
          <q-list bordered separator class="rounded-borders">
            <q-item v-if="loadingAnalyzedAssets">
              <q-item-section class="flex items-center q-py-lg">
                <q-spinner color="primary" size="3em" />
                <div class="q-mt-md text-grey-7">Loading assets...</div>
              </q-item-section>
            </q-item>
            <q-item v-else-if="analyzedAssets.length === 0">
              <q-item-section class="text-center q-py-lg text-grey-7">
                <q-icon name="info" size="2em" class="q-mb-sm" />
                <div>No image/audio assets found.</div>
              </q-item-section>
            </q-item>
            <q-item v-for="asset in analyzedAssets" :key="asset.path" class="q-py-md">
              <q-item-section>
                <q-item-label class="text-weight-medium">{{ asset.path.split('/').pop() }}</q-item-label>
                <q-item-label caption>{{ asset.path }} • {{ asset.mime }}</q-item-label>

                <div v-if="isImageAsset(asset)" class="q-mt-md">
                  <div class="row q-col-gutter-lg">
                    <div class="col-12 col-sm-6">
                      <div class="text-overline text-grey-7">Original</div>
                      <div v-if="assetResolutions[asset.path]?.original" class="text-caption text-grey-6 q-mb-xs">
                        {{ assetResolutions[asset.path]?.original }}px
                      </div>
                      <q-img :src="assetOriginalPreviewUrl(asset)" :alt="`original-${asset.path}`" fit="contain"
                        class="rounded-borders bg-grey-2 shadow-1" style="width: 100%; height: 160px"
                        @load="(src) => onOriginalImageLoad(asset.path, src)">
                        <template v-slot:error>
                          <div class="absolute-full flex flex-center bg-negative text-white">
                            Cannot load
                          </div>
                        </template>
                      </q-img>
                    </div>
                    <div class="col-12 col-sm-6">
                      <div class="text-overline text-grey-7">Replacement</div>
                      <div v-if="assetResolutions[asset.path]?.replacement" class="text-caption text-grey-6 q-mb-xs">
                        {{ assetResolutions[asset.path]?.replacement }}px
                      </div>
                      <div v-if="hasReplacement(asset.path)" class="relative-position">
                        <q-img :src="assetReplacementPreviewUrl(asset)" :alt="`replacement-${asset.path}`" fit="contain"
                          class="rounded-borders bg-grey-2 shadow-1" style="width: 100%; height: 160px"
                          @load="(src) => onReplacementImageLoad(asset.path, src)">
                          <template v-slot:loading>
                            <q-spinner-oval color="white" />
                          </template>
                        </q-img>
                        <q-btn round dense color="negative" icon="delete" class="absolute-top-right q-ma-xs"
                          @click="deleteReplacementAsset(asset)">
                          <q-tooltip>Delete replacement</q-tooltip>
                        </q-btn>
                      </div>
                      <div v-else
                        class="flex items-center justify-center rounded-borders bg-grey-3 text-grey-6 border-dashed"
                        style="width: 100%; height: 160px; border: 2px dashed #bdbdbd">
                        <q-icon name="add_photo_alternate" size="2em" />
                        <div class="q-ml-sm">No replacement</div>
                      </div>
                    </div>
                  </div>

                  <div class="row q-col-gutter-sm items-center q-mt-md">
                    <div class="col">
                      <q-file dense outlined accept="image/*" label="Choose replacement"
                        :model-value="replacementFiles[asset.path] || null"
                        @update:model-value="(file) => setReplacementFile(asset.path, file)">
                        <template v-slot:prepend>
                          <q-icon name="attach_file" />
                        </template>
                      </q-file>
                    </div>
                    <div class="col-auto">
                      <q-btn color="primary" icon="cloud_upload" label="Upload" unelevated
                        :loading="uploadingAssetPath === asset.path" :disable="!replacementFiles[asset.path] || uploadingAssetPath === asset.path
                          " @click="uploadReplacementAsset(asset)" />
                    </div>
                  </div>
                </div>
              </q-item-section>
            </q-item>
          </q-list>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn v-if="isEditMode" flat label="Save" color="primary" v-close-popup @click="updateGame" />
          <q-btn v-else flat label="Add" color="green" :loading="isAddingGame" @click="addGame" />
        </q-card-actions>
      </q-card>
    </q-dialog>
    <!-- Workflow Status Dialog -->
    <q-dialog v-model="workflowModalOpen" persistent>
      <q-card class="w-120 q-pa-lg text-center">
        <q-card-section>
          <div class="text-h6 q-mb-md">Update Status</div>

          <div v-if="workflowStatus !== 'completed'" class="flex flex-col items-center">
            <q-spinner-orbit color="primary" size="4em" class="q-mb-lg" />
            <div class="text-body1">
              deploying games, please wait.<br />
              <strong class="text-negative">Do not (re)start the pi yet</strong>
            </div>
            <div class="text-caption text-grey-7 q-mt-md">
              Status: {{ workflowStatus || 'Initializing...' }}
            </div>

            <div v-if="workflowProgress.total_steps > 0" class="w-full q-mt-lg">
              <div class="row justify-between items-center q-mb-xs">
                <div class="text-caption text-weight-bold">
                  Step {{ workflowProgress.completed_steps + 1 }}/{{ workflowProgress.total_steps }}
                </div>
                <div class="text-caption text-grey-7">
                  {{ Math.round((workflowProgress.completed_steps / workflowProgress.total_steps) * 100) }}%
                </div>
              </div>
              <q-linear-progress :value="workflowProgress.completed_steps / workflowProgress.total_steps"
                color="primary" class="q-mb-sm" />
              <div class="text-caption text-grey-6 italic">
                {{ workflowProgress.current_step }}
              </div>
            </div>
          </div>

          <div v-else class="flex flex-col items-center">
            <template v-if="workflowConclusion === 'success'">
              <q-icon name="check_circle" color="positive" size="4em" class="q-mb-lg" />
              <div class="text-body1">
                Restart the pi with an internet connection to update the game selection.
              </div>
            </template>
            <template v-else>
              <q-icon name="error" color="negative" size="4em" class="q-mb-lg" />
              <div class="text-body1 text-negative">
                Workflow failed or was cancelled.
              </div>
              <div class="text-caption text-grey-7 q-mt-md">
                Conclusion: {{ workflowConclusion }}
              </div>
            </template>
          </div>
        </q-card-section>

        <q-card-actions align="center" class="q-mt-md">
          <q-btn v-if="workflowStatus === 'completed'" label="Close" color="primary" flat
            @click="workflowModalOpen = false" />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup lang="ts">
import { ref, reactive, onUnmounted } from 'vue';
import { useQuasar } from 'quasar';
import GameCard from '../components/GameCard.vue';
import { api } from 'boot/axios';
import { useNotificationStore } from 'src/stores/notification';

const notificationStore = useNotificationStore();

interface Game {
  id: string;
  name: string;
  description?: string;
  is_active: boolean;
}

interface AnalyzedAsset {
  path: string;
  mime: string;
  zip_file: string;
}

const $q = useQuasar();

const isLoading = ref(true);
const data = reactive<Game[]>([]);
const confirm = ref(false);
const isEditMode = ref(false);
const modalGame = reactive<{ id: string | undefined; name: string; description: string; is_active: boolean }>({
  id: undefined,
  name: '',
  description: '',
  is_active: true,
});
const analyzedAssets = ref<AnalyzedAsset[]>([]);
const loadingAnalyzedAssets = ref(false);
const replacementPaths = ref<Set<string>>(new Set());
const replacementFiles = reactive<Record<string, File | null>>({});
const uploadingAssetPath = ref<string | null>(null);
const uploaderRef = ref();
const isAddingGame = ref(false);
const apiKey = import.meta.env.VITE_API_KEY;

const assetResolutions = reactive<Record<string, { original?: string, replacement?: string }>>({});

function onOriginalImageLoad(path: string, src: string) {
  const img = new Image();
  img.onload = () => {
    if (!assetResolutions[path]) assetResolutions[path] = {};
    assetResolutions[path].original = `${img.naturalWidth}x${img.naturalHeight}`;
  };
  img.src = src;
}

function onReplacementImageLoad(path: string, src: string) {
  const img = new Image();
  img.onload = () => {
    if (!assetResolutions[path]) assetResolutions[path] = {};
    assetResolutions[path].replacement = `${img.naturalWidth}x${img.naturalHeight}`;
  };
  img.src = src;
}

// Workflow feedback state
const workflowModalOpen = ref(false);
const workflowStatus = ref<string | null>(null);
const workflowConclusion = ref<string | null>(null);
const workflowProgress = reactive({
  total_steps: 0,
  completed_steps: 0,
  current_step: ''
});
let triggerTime: number | null = null;
let pollingTimeout: number | null = null;

// Cleanup helper
function stopPolling() {
  if (pollingTimeout) {
    clearTimeout(pollingTimeout);
    pollingTimeout = null;
  }
}

onUnmounted(() => {
  stopPolling();
});

function isImageAsset(asset: AnalyzedAsset) {
  return asset.mime.startsWith('image/');
}

function assetOriginalPreviewUrl(asset: AnalyzedAsset) {
  if (!modalGame.id) return '';
  return `${api.defaults.baseURL}/games/${modalGame.id}/original/${encodeURI(asset.path)}?api_key=${apiKey}`;
}

function assetReplacementPreviewUrl(asset: AnalyzedAsset) {
  if (!modalGame.id) return '';
  return `${api.defaults.baseURL}/games/${modalGame.id}/replacement/${encodeURI(asset.path)}?api_key=${apiKey}&t=${Date.now()}`;
}

function hasReplacement(originalPath: string) {
  return replacementPaths.value.has(originalPath);
}

function setReplacementFile(originalPath: string, file: File | File[] | null) {
  if (Array.isArray(file)) {
    replacementFiles[originalPath] = file[0] ?? null;
    return;
  }
  replacementFiles[originalPath] = file;
}

async function loadAssetOverrides(gameId: string) {
  const response = await api.get(`/games/${gameId}/asset-overrides`);
  const paths = new Set<string>(
    (response.data.overrides ?? []).map((o: { original_path: string }) => o.original_path),
  );
  replacementPaths.value = paths;
}

function resetModal() {
  confirm.value = false;
  isEditMode.value = false;
  modalGame.id = undefined;
  modalGame.name = '';
  modalGame.description = '';
  modalGame.is_active = true;
  analyzedAssets.value = [];
  loadingAnalyzedAssets.value = false;
  replacementPaths.value = new Set();
  Object.keys(replacementFiles).forEach((k) => {
    delete replacementFiles[k];
  });
  uploadingAssetPath.value = null;
  Object.keys(assetResolutions).forEach(k => delete assetResolutions[k]);
}

async function addGame() {
  const uploader = uploaderRef.value;
  if (!uploader || uploader.files.length === 0) {
    notificationStore.notify({ type: 'negative', message: 'Please select a ZIP file to upload.' });
    return;
  }

  isAddingGame.value = true;
  try {
    // Step 1: Create the game
    const gameResp = await api.post('/games', {
      name: modalGame.name,
      description: modalGame.description,
      is_active: modalGame.is_active
    });
    const newGame = gameResp.data.game;
    // Step 2: Upload the ZIP file
    const formData = new FormData();
    formData.append('file', uploader.files[0]);
    await api.post(`/file-uploads/upload-zip?game_id=${newGame.id}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    await loadData();
    confirm.value = false;
    resetModal();
  } catch (err) {
    console.error(err);
    notificationStore.notify({ type: 'negative', message: 'Failed to add game.' });
  } finally {
    isAddingGame.value = false;
  }
}

async function onEditGame(game: Game) {
  modalGame.id = game.id;
  modalGame.name = game.name;
  modalGame.description = game.description || '';
  modalGame.is_active = game.is_active;
  isEditMode.value = true;
  confirm.value = true;
  Object.keys(assetResolutions).forEach(k => delete assetResolutions[k]);

  loadingAnalyzedAssets.value = true;
  analyzedAssets.value = [];
  try {
    const [assetsResponse] = await Promise.all([
      api.get(`/games/${game.id}/analyzed-assets`),
      loadAssetOverrides(game.id),
    ]);
    analyzedAssets.value = assetsResponse.data.media_files ?? [];
  } catch {
    notificationStore.notify({ type: 'negative', message: 'Could not load analyzed assets.' });
  } finally {
    loadingAnalyzedAssets.value = false;
  }
}

async function uploadReplacementAsset(asset: AnalyzedAsset) {
  if (!modalGame.id) return;
  const file = replacementFiles[asset.path];
  if (!file) {
    notificationStore.notify({ type: 'warning', message: 'Select a file first.' });
    return;
  }

  uploadingAssetPath.value = asset.path;
  try {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('original_path', asset.path);

    await api.post(`/games/${modalGame.id}/upload-asset`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });

    replacementPaths.value = new Set([...replacementPaths.value, asset.path]);
    replacementFiles[asset.path] = null;
    notificationStore.notify({ type: 'positive', message: 'Replacement uploaded.' });
  } catch {
    notificationStore.notify({ type: 'negative', message: 'Could not upload replacement.' });
  } finally {
    uploadingAssetPath.value = null;
  }
}

function deleteReplacementAsset(asset: AnalyzedAsset) {
  if (!modalGame.id) return;

  $q.dialog({
    title: 'Confirm deletion',
    message: `Are you sure you want to delete the replacement for ${asset.path}?`,
    cancel: true,
    ok: {
      label: 'Delete',
      color: 'negative',
    },
  }).onOk(() => {
    void (async () => {
      try {
        await api.delete(`/games/${modalGame.id}/asset-override`, {
          params: { original_path: asset.path },
        });

        replacementPaths.value.delete(asset.path);
        // Trigger a re-render of the replacement preview if needed,
        // though replacementPaths update should be enough if we use it in v-if
        notificationStore.notify({ type: 'positive', message: 'Replacement deleted.' });

        // Clear resolution
        const res = assetResolutions[asset.path];
        if (res) {
          delete res.replacement;
        }
      } catch {
        notificationStore.notify({ type: 'negative', message: 'Could not delete replacement.' });
      }
    })();
  });
}

async function updateGame() {
  try {
    const response = await api.put(`/games/${modalGame.id}`, {
      name: modalGame.name,
      description: modalGame.description,
    });

    const updatedGame = response.data.game;
    if (!updatedGame) return;

    await loadData();
  } catch (err) {
    // handle or log error
    console.error(err);
  }
}

async function toggleActive(game: Game, active: boolean) {
  try {
    await api.put(`/games/${game.id}`, {
      id: game.id,
      name: game.name,
      description: game.description,
      is_active: active,
    });
    game.is_active = active;
    notificationStore.notify({
      type: 'positive',
      message: `Game ${game.name} is now ${active ? 'active' : 'inactive'}.`,
    });
  } catch (err) {
    console.error(err);
    notificationStore.notify({ type: 'negative', message: 'Failed to update active status.' });
  }
}

function deleteGame(params: { id: string }) {
  $q.dialog({
    title: 'Confirm deletion',
    message: 'Are you sure you want to delete this game? This action cannot be undone.',
    cancel: true,
    ok: {
      label: 'Delete',
      color: 'negative',
    },
  })
    .onOk(() => {
      void (async () => {
        try {
          await api.delete(`/games/${params.id}`);
          await loadData();
        } catch (err) {
          console.error(err);
        }
      })();
    })
    .onCancel(() => {
      // console.log('>>>> Cancel')
    })
    .onDismiss(() => {
      // console.log('I am triggered on both OK and Cancel')
    });
}

async function loadData() {
  isLoading.value = true;
  try {
    const response = await api.get('/games');
    data.splice(0, data.length, ...response.data.games);
  } catch (err) {
    console.error(err);
  } finally {
    isLoading.value = false;
  }
}

async function pollWorkflowStatus() {
  // If modal was closed in the meantime, don't ping or schedule more
  if (!workflowModalOpen.value) {
    stopPolling();
    return;
  }

  try {
    const response = await api.get('/trigger-build/workflow-status');
    const run = response.data;

    // Ignore runs created before we clicked the button
    if (run.created_at) {
      const runCreated = new Date(run.created_at).getTime();
      if (triggerTime && runCreated < triggerTime) {
        workflowStatus.value = 'waiting for start...';
      } else {
        workflowStatus.value = run.status;
        workflowConclusion.value = run.conclusion;

        if (run.progress) {
          workflowProgress.total_steps = run.progress.total_steps;
          workflowProgress.completed_steps = run.progress.completed_steps;
          workflowProgress.current_step = run.progress.current_step;
        }
      }
    }

    // Continue polling if not completed
    if (workflowStatus.value !== 'completed') {
      pollingTimeout = window.setTimeout(() => {
        void pollWorkflowStatus();
      }, 500);
    } else {
      stopPolling();
    }
  } catch (err) {
    console.error('Error polling workflow status:', err);
    stopPolling();
    notificationStore.notify({
      type: 'negative',
      message: 'Failed to check update status. Please check your GitHub App permissions (Actions: Read-only).',
    });
    workflowModalOpen.value = false;
  }
}

async function updatePi() {
  try {
    workflowStatus.value = 'starting';
    workflowConclusion.value = null;
    workflowProgress.total_steps = 0;
    workflowProgress.completed_steps = 0;
    workflowProgress.current_step = '';

    triggerTime = Date.now() - 10000; // Give some buffer for clock skew
    workflowModalOpen.value = true;

    await api.post('/trigger-build/trigger-workflow');

    // Start polling
    stopPolling();
    await pollWorkflowStatus();

  } catch (err) {
    console.error(err);
    notificationStore.notify({ type: 'negative', message: 'Failed to trigger update.' });
    workflowModalOpen.value = false;
  }
}

loadData().catch((err) => {
  console.error(err);
});

// Test notification on load
// notificationStore.notify({
//   type: 'info',
//   message: 'Welcome to the Arcade Cabinet Management! This is a test notification.'
// });
</script>
