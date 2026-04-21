<template>
  <q-page class="container mx-auto px-5 md:px-0">
    <div class="flex justify-between mt-10">
      <q-btn
        unelevated
        icon="rocket_launch"
        color="primary"
        label="Update Pi"
        :ripple="false"
        @click="updatePi"
      />
      <q-btn
        color="green"
        icon="add"
        label="Add Game"
        unelevated
        :ripple="false"
        @click="confirm = true"
      />
    </div>

    <!-- Game cards -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
      <game-card
        v-for="game in data"
        :key="game.id"
        :title="game.name"
        :modal="modalGame"
        :id="game.id"
        @edit="onEditGame(game)"
        @delete="deleteGame(game)"
      />
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
          <!-- Show uploader only in add mode -->
          <q-uploader
            v-if="!isEditMode"
            ref="uploaderRef"
            accept=".zip"
            label="Upload ZIP folder"
            field-name="file"
            :auto-upload="false"
            :hide-upload-btn="true"
          />
          <div v-else>
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
                  <q-item-label class="text-weight-medium">{{ asset.path }}</q-item-label>
                  <q-item-label caption>{{ asset.mime }}</q-item-label>

                  <div v-if="isImageAsset(asset)" class="q-mt-md">
                    <div class="row q-col-gutter-lg">
                      <div class="col-12 col-sm-6">
                        <div class="text-overline q-mb-xs text-grey-7">Original</div>
                        <q-img
                          :src="assetOriginalPreviewUrl(asset)"
                          :alt="`original-${asset.path}`"
                          fit="contain"
                          class="rounded-borders bg-grey-2 shadow-1"
                          style="width: 100%; height: 160px"
                        >
                          <template v-slot:error>
                            <div class="absolute-full flex flex-center bg-negative text-white">
                              Cannot load
                            </div>
                          </template>
                        </q-img>
                      </div>
                      <div class="col-12 col-sm-6">
                        <div class="text-overline q-mb-xs text-grey-7">Replacement</div>
                        <q-img
                          v-if="hasReplacement(asset.path)"
                          :src="assetReplacementPreviewUrl(asset)"
                          :alt="`replacement-${asset.path}`"
                          fit="contain"
                          class="rounded-borders bg-grey-2 shadow-1"
                          style="width: 100%; height: 160px"
                        >
                          <template v-slot:loading>
                            <q-spinner-oval color="white" />
                          </template>
                        </q-img>
                        <div
                          v-else
                          class="flex items-center justify-center rounded-borders bg-grey-3 text-grey-6 border-dashed"
                          style="width: 100%; height: 160px; border: 2px dashed #bdbdbd"
                        >
                          <q-icon name="add_photo_alternate" size="2em" />
                          <div class="q-ml-sm">No replacement</div>
                        </div>
                      </div>
                    </div>

                    <div class="row q-col-gutter-sm items-center q-mt-md">
                      <div class="col">
                        <q-file
                          dense
                          outlined
                          accept="image/*"
                          label="Choose replacement"
                          :model-value="replacementFiles[asset.path] || null"
                          @update:model-value="(file) => setReplacementFile(asset.path, file)"
                        >
                          <template v-slot:prepend>
                            <q-icon name="attach_file" />
                          </template>
                        </q-file>
                      </div>
                      <div class="col-auto">
                        <q-btn
                          color="primary"
                          icon="cloud_upload"
                          label="Upload"
                          unelevated
                          :loading="uploadingAssetPath === asset.path"
                          :disable="!replacementFiles[asset.path] || uploadingAssetPath === asset.path"
                          @click="uploadReplacementAsset(asset)"
                        />
                      </div>
                    </div>
                  </div>
                </q-item-section>
              </q-item>
            </q-list>
          </div>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn
            v-if="isEditMode"
            flat
            label="Save"
            color="primary"
            v-close-popup
            @click="updateGame"
          />
          <q-btn v-else flat label="Add" color="green" v-close-popup @click="addGame" />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue';
import { useQuasar } from 'quasar';
import GameCard from '../components/GameCard.vue';
import { api } from 'boot/axios';

interface Game {
  id: string;
  name: string;
}

interface AnalyzedAsset {
  path: string;
  mime: string;
  zip_file: string;
}

const $q = useQuasar();

const data = reactive<Game[]>([]);
const confirm = ref(false);
const isEditMode = ref(false);
const modalGame = reactive<{ id: string | undefined; name: string }>({ id: undefined, name: '' });
const analyzedAssets = ref<AnalyzedAsset[]>([]);
const loadingAnalyzedAssets = ref(false);
const replacementPaths = ref<Set<string>>(new Set());
const replacementFiles = reactive<Record<string, File | null>>({});
const uploadingAssetPath = ref<string | null>(null);
const uploaderRef = ref();

function isImageAsset(asset: AnalyzedAsset) {
  return asset.mime.startsWith('image/');
}

function assetOriginalPreviewUrl(asset: AnalyzedAsset) {
  if (!modalGame.id) return '';
  return `${api.defaults.baseURL}/games/${modalGame.id}/original/${encodeURI(asset.path)}`;
}

function assetReplacementPreviewUrl(asset: AnalyzedAsset) {
  if (!modalGame.id) return '';
  return `${api.defaults.baseURL}/games/${modalGame.id}/replacement/${encodeURI(asset.path)}?t=${Date.now()}`;
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
  const paths = new Set<string>((response.data.overrides ?? []).map((o: { original_path: string }) => o.original_path));
  replacementPaths.value = paths;
}

function resetModal() {
  confirm.value = false;
  isEditMode.value = false;
  modalGame.id = undefined;
  modalGame.name = '';
  analyzedAssets.value = [];
  loadingAnalyzedAssets.value = false;
  replacementPaths.value = new Set();
  Object.keys(replacementFiles).forEach((k) => {
    delete replacementFiles[k];
  });
  uploadingAssetPath.value = null;
}

async function addGame() {
  const uploader = uploaderRef.value;
  if (!uploader || uploader.files.length === 0) {
    $q.notify({ type: 'negative', message: 'Please select a ZIP file to upload.' });
    return;
  }
  // Step 1: Create the game
  const gameResp = await api.post('/games', { name: modalGame.name });
  const newGame = gameResp.data.game;
  // Step 2: Upload the ZIP file
  const formData = new FormData();
  formData.append('file', uploader.files[0]);
  await api.post(`/file-uploads/upload-zip?game_id=${newGame.id}`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  data.push(newGame);
  confirm.value = false;
  resetModal();
}

async function onEditGame(game: Game) {
  modalGame.id = game.id;
  modalGame.name = game.name;
  isEditMode.value = true;
  confirm.value = true;

  loadingAnalyzedAssets.value = true;
  analyzedAssets.value = [];
  try {
    const [assetsResponse] = await Promise.all([
      api.get(`/games/${game.id}/analyzed-assets`),
      loadAssetOverrides(game.id),
    ]);
    analyzedAssets.value = assetsResponse.data.media_files ?? [];
  } catch {
    $q.notify({ type: 'negative', message: 'Could not load analyzed assets.' });
  } finally {
    loadingAnalyzedAssets.value = false;
  }
}

async function uploadReplacementAsset(asset: AnalyzedAsset) {
  if (!modalGame.id) return;
  const file = replacementFiles[asset.path];
  if (!file) {
    $q.notify({ type: 'warning', message: 'Select a file first.' });
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
    $q.notify({ type: 'positive', message: 'Replacement uploaded.' });
  } catch {
    $q.notify({ type: 'negative', message: 'Could not upload replacement.' });
  } finally {
    uploadingAssetPath.value = null;
  }
}

function updateGame() {
  api.put(`/games/${modalGame.id}`, { id: modalGame.id, name: modalGame.name }).then((response) => {
    const updatedGame = response.data.game;
    if (!updatedGame) return;
    const idx = data.findIndex((g) => g.id === updatedGame.id);
    if (idx !== -1 && data[idx]) {
      data[idx].name = updatedGame.name;
    }
  });
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
      api.delete(`/games/${params.id}`).then(() => {
        const idx = data.findIndex((g) => g.id === params.id);
        if (idx !== -1) {
          data.splice(idx, 1);
        }
      });
    })
    .onCancel(() => {
      // console.log('>>>> Cancel')
    })
    .onDismiss(() => {
      // console.log('I am triggered on both OK and Cancel')
    });
}

function loadData() {
  api.get('/games').then((response) => {
    data.splice(0, data.length, ...response.data.games);
  });
}

function updatePi() {
  api.post('/trigger-build/trigger-workflow').then(() => {
    $q.notify({ type: 'positive', message: 'Pi update triggered.' });
  });
}

// Load data on component creation
loadData();
</script>
