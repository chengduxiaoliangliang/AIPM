<template>
  <div
    ref="containerRef"
    class="aether-sprite-container"
    :class="[modeClass, { 'is-interactive': interactive }]"
    @pointermove="onPointerMove"
    @pointerleave="onPointerLeave"
    @pointerdown="onPointerDown"
  >
    <canvas ref="canvasRef" class="aether-canvas"></canvas>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, computed } from 'vue'
import * as THREE from 'three'
import { defaultNoise } from './simplexNoise'

// --- Props & Emits ---
interface SpriteProps {
  mode?: 'mini' | 'card' | 'fullscreen'
  state?: 'idle' | 'curious' | 'thinking' | 'typing' | 'bouncy'
  theme?: 'nebula' | 'aurora' | 'sunset' | 'cyber' | 'gold'
  interactive?: boolean
  particleCount?: number
  noiseStrength?: number
  springStiffness?: number
  springDamping?: number
}

const props = withDefaults(defineProps<SpriteProps>(), {
  mode: 'mini',
  state: 'idle',
  theme: 'nebula',
  interactive: true,
  particleCount: undefined,
  noiseStrength: 0.14,
  springStiffness: 130,
  springDamping: 11
})

const emit = defineEmits<{
  (e: 'click-sprite'): void
  (e: 'bounce-finish'): void
}>()

const containerRef = ref<HTMLDivElement>()
const canvasRef = ref<HTMLCanvasElement>()
const modeClass = computed(() => `mode-${props.mode}`)

// --- Palette Color Definition ---
interface ThemePalette {
  primary: THREE.Color
  secondary: THREE.Color
  core: THREE.Color
  particles: THREE.Color
  eyes: THREE.Color
}

const THEMES: Record<string, ThemePalette> = {
  nebula: {
    primary: new THREE.Color(0x4f46e5),   // Indigo
    secondary: new THREE.Color(0x06b6d4), // Cyan
    core: new THREE.Color(0xffffff),
    particles: new THREE.Color(0x818cf8),
    eyes: new THREE.Color(0x67e8f9)
  },
  aurora: {
    primary: new THREE.Color(0x059669),   // Emerald
    secondary: new THREE.Color(0x22d3ee), // Cyan
    core: new THREE.Color(0xf0fdf4),
    particles: new THREE.Color(0x34d399),
    eyes: new THREE.Color(0xa7f3d0)
  },
  sunset: {
    primary: new THREE.Color(0xdb2777),   // Pink
    secondary: new THREE.Color(0xf59e0b), // Amber
    core: new THREE.Color(0xffedd5),
    particles: new THREE.Color(0xfb7185),
    eyes: new THREE.Color(0xfef08a)
  },
  cyber: {
    primary: new THREE.Color(0x2563eb),   // Royal Blue
    secondary: new THREE.Color(0xf43f5e), // Rose Neon
    core: new THREE.Color(0xffffff),
    particles: new THREE.Color(0xa855f7),
    eyes: new THREE.Color(0x38bdf8)
  },
  gold: {
    primary: new THREE.Color(0xd97706),   // Amber Gold
    secondary: new THREE.Color(0xfacc15), // Yellow
    core: new THREE.Color(0xfffbeb),
    particles: new THREE.Color(0xfde047),
    eyes: new THREE.Color(0xfef9c3)
  }
}

// --- 3D Scene Resources ---
let renderer: THREE.WebGLRenderer | null = null
let scene: THREE.Scene | null = null
let camera: THREE.PerspectiveCamera | null = null
let animFrameId: number | null = null
let resizeObserver: ResizeObserver | null = null

// Meshes & Groups
let spriteRoot: THREE.Group
let bodyMesh: THREE.Mesh
let bodyGeo: THREE.IcosahedronGeometry
let bodyOriginalPos: THREE.BufferAttribute
let bodyMat: THREE.ShaderMaterial
let coreMesh: THREE.Mesh
let eyeGroup: THREE.Group
let leftEye: THREE.Mesh
let rightEye: THREE.Mesh
let leftPupil: THREE.Mesh
let rightPupil: THREE.Mesh
let leftEar: THREE.Mesh
let rightEar: THREE.Mesh
let particlePoints: THREE.Points
let particleGeo: THREE.BufferGeometry

// Simulation State
interface ParticleMeta {
  radius: number
  theta: number
  phi: number
  speedTheta: number
  speedPhi: number
  baseRadius: number
  orbitOffset: number
}
let particleData: ParticleMeta[] = []

const mouse = {
  x: 0,
  y: 0,
  targetX: 0,
  targetY: 0,
  isInside: false
}

const spring = {
  y: 0,
  targetY: 0,
  velY: 0,
  scaleY: 1,
  targetScaleY: 1,
  velScaleY: 0
}

let saccadeTimer = 0
const saccadeOffset = { x: 0, y: 0 }
let blinkTimer = 0
let clock = new THREE.Clock()
let burstIntensity = 0

// --- Helpers ---
function createParticleTexture(): THREE.Texture {
  const canvas = document.createElement('canvas')
  canvas.width = 64
  canvas.height = 64
  const ctx = canvas.getContext('2d')!
  const grad = ctx.createRadialGradient(32, 32, 0, 32, 32, 32)
  grad.addColorStop(0, 'rgba(255, 255, 255, 1)')
  grad.addColorStop(0.25, 'rgba(216, 180, 254, 0.85)')
  grad.addColorStop(0.65, 'rgba(129, 140, 248, 0.35)')
  grad.addColorStop(1, 'rgba(0, 0, 0, 0)')
  ctx.fillStyle = grad
  ctx.fillRect(0, 0, 64, 64)
  return new THREE.CanvasTexture(canvas)
}

function initScene() {
  if (!containerRef.value || !canvasRef.value) return

  let width = containerRef.value.clientWidth
  let height = containerRef.value.clientHeight
  if (!width || width <= 10) width = props.mode === 'mini' ? 68 : 640
  if (!height || height <= 10) height = props.mode === 'mini' ? 68 : 500

  // 1. Scene & Camera
  scene = new THREE.Scene()
  camera = new THREE.PerspectiveCamera(40, width / height, 0.1, 100)
  camera.position.z = props.mode === 'mini' ? 5.8 : 6.2

  // 2. Renderer
  renderer = new THREE.WebGLRenderer({
    canvas: canvasRef.value,
    antialias: true,
    alpha: true,
    powerPreference: 'high-performance'
  })
  renderer.setSize(width, height)
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))

  // 3. Sprite Root Container
  spriteRoot = new THREE.Group()
  scene.add(spriteRoot)

  // 4. Jelly Body with Custom Shader
  const detail = props.mode === 'mini' ? 4 : 5
  bodyGeo = new THREE.IcosahedronGeometry(1.15, detail)
  bodyOriginalPos = bodyGeo.attributes.position.clone() as THREE.BufferAttribute

  const activeTheme = THEMES[props.theme] || THEMES.nebula

  bodyMat = new THREE.ShaderMaterial({
    uniforms: {
      uTime: { value: 0 },
      uColorA: { value: activeTheme.primary.clone() },
      uColorB: { value: activeTheme.secondary.clone() },
      uGlowColor: { value: activeTheme.core.clone() },
      uFresnelPower: { value: 2.1 },
      uOpacity: { value: 0.9 }
    },
    vertexShader: `
      varying vec3 vNormal;
      varying vec3 vViewPosition;
      void main() {
        vNormal = normalize(normalMatrix * normal);
        vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
        vViewPosition = -mvPosition.xyz;
        gl_Position = projectionMatrix * mvPosition;
      }
    `,
    fragmentShader: `
      uniform vec3 uColorA;
      uniform vec3 uColorB;
      uniform vec3 uGlowColor;
      uniform float uFresnelPower;
      uniform float uOpacity;
      varying vec3 vNormal;
      varying vec3 vViewPosition;
      void main() {
        vec3 normal = normalize(vNormal);
        vec3 viewDir = normalize(vViewPosition);
        float fresnel = pow(1.0 - max(dot(viewDir, normal), 0.0), uFresnelPower);
        vec3 baseColor = mix(uColorA, uColorB, normal.y * 0.5 + 0.5);
        vec3 finalColor = mix(baseColor, uGlowColor, fresnel * 0.85);
        gl_FragColor = vec4(finalColor, uOpacity);
      }
    `,
    transparent: true,
    depthWrite: false
  })

  bodyMesh = new THREE.Mesh(bodyGeo, bodyMat)
  spriteRoot.add(bodyMesh)

  // 5. Core Nucleus (Heart Pulse)
  const coreGeo = new THREE.SphereGeometry(0.5, 24, 24)
  const coreMat = new THREE.MeshBasicMaterial({
    color: activeTheme.core,
    transparent: true,
    opacity: 0.88,
    blending: THREE.AdditiveBlending
  })
  coreMesh = new THREE.Mesh(coreGeo, coreMat)
  spriteRoot.add(coreMesh)

  // 6. Expressive Bioluminescent Eyes
  eyeGroup = new THREE.Group()
  eyeGroup.position.set(0, 0.14, 1.02)
  spriteRoot.add(eyeGroup)

  const eyeGeo = new THREE.SphereGeometry(0.13, 20, 20)
  const eyeMat = new THREE.MeshBasicMaterial({ color: 0x0f172a })

  const pupilGeo = new THREE.SphereGeometry(0.065, 16, 16)
  const pupilMat = new THREE.MeshBasicMaterial({
    color: activeTheme.eyes,
    transparent: true,
    opacity: 0.95
  })

  // Left Eye
  leftEye = new THREE.Mesh(eyeGeo, eyeMat)
  leftEye.position.x = -0.34
  leftPupil = new THREE.Mesh(pupilGeo, pupilMat)
  leftPupil.position.z = 0.085
  leftEye.add(leftPupil)
  eyeGroup.add(leftEye)

  // Right Eye
  rightEye = new THREE.Mesh(eyeGeo, eyeMat)
  rightEye.position.x = 0.34
  rightPupil = new THREE.Mesh(pupilGeo, pupilMat.clone())
  rightPupil.position.z = 0.085
  rightEye.add(rightPupil)
  eyeGroup.add(rightEye)

  // 7. Dynamic Energetic Ears / Wings (Small floating celestial orbs)
  const earGeo = new THREE.SphereGeometry(0.18, 16, 16)
  const earMat = new THREE.MeshBasicMaterial({
    color: activeTheme.secondary,
    transparent: true,
    opacity: 0.75,
    blending: THREE.AdditiveBlending
  })
  leftEar = new THREE.Mesh(earGeo, earMat)
  leftEar.position.set(-0.95, 0.85, -0.2)
  leftEar.scale.set(0.6, 1.2, 0.6)
  spriteRoot.add(leftEar)

  rightEar = new THREE.Mesh(earGeo, earMat.clone())
  rightEar.position.set(0.95, 0.85, -0.2)
  rightEar.scale.set(0.6, 1.2, 0.6)
  spriteRoot.add(rightEar)

  // 8. Particle Swarm Aura
  const count = props.particleCount || (props.mode === 'mini' ? 450 : 1200)
  particleGeo = new THREE.BufferGeometry()
  const pPositions = new Float32Array(count * 3)
  particleData = []

  for (let i = 0; i < count; i++) {
    const baseRadius = 1.35 + Math.random() * 0.85
    const theta = Math.random() * Math.PI * 2
    const phi = Math.acos(2 * Math.random() - 1)

    pPositions[i * 3] = baseRadius * Math.sin(phi) * Math.cos(theta)
    pPositions[i * 3 + 1] = baseRadius * Math.sin(phi) * Math.sin(theta)
    pPositions[i * 3 + 2] = baseRadius * Math.cos(phi)

    particleData.push({
      radius: baseRadius,
      baseRadius,
      theta,
      phi,
      speedTheta: (Math.random() - 0.5) * 0.9,
      speedPhi: (Math.random() - 0.5) * 0.7,
      orbitOffset: Math.random() * Math.PI * 2
    })
  }

  particleGeo.setAttribute('position', new THREE.BufferAttribute(pPositions, 3))

  const particleMat = new THREE.PointsMaterial({
    size: props.mode === 'mini' ? 0.16 : 0.13,
    map: createParticleTexture(),
    transparent: true,
    color: activeTheme.particles,
    blending: THREE.AdditiveBlending,
    depthWrite: false
  })

  particlePoints = new THREE.Points(particleGeo, particleMat)
  spriteRoot.add(particlePoints)

  // Setup Resize Observer
  resizeObserver = new ResizeObserver(() => {
    handleResize()
  })
  resizeObserver.observe(containerRef.value)

  // Start animation loop
  clock.start()
  animate()
}

function handleResize() {
  if (!containerRef.value || !renderer || !camera) return
  const width = containerRef.value.clientWidth
  const height = containerRef.value.clientHeight
  if (width === 0 || height === 0) return

  camera.aspect = width / height
  camera.updateProjectionMatrix()
  renderer.setSize(width, height)
}

// --- Animation & Physics Solver ---
function animate() {
  animFrameId = requestAnimationFrame(animate)
  if (!renderer || !scene || !camera) return

  const dt = Math.min(clock.getDelta(), 0.05)
  const time = clock.getElapsedTime()

  // 1. Mouse Smooth Pursuit
  mouse.x += (mouse.targetX - mouse.x) * 5.0 * dt
  mouse.y += (mouse.targetY - mouse.y) * 5.0 * dt

  // 2. Spring Physics Solver (Squash & Stretch)
  const k = props.springStiffness
  const d = props.springDamping

  const forceY = -k * (spring.y - spring.targetY) - d * spring.velY
  spring.velY += forceY * dt
  spring.y += spring.velY * dt

  const forceScale = -k * (spring.scaleY - spring.targetScaleY) - d * spring.velScaleY
  spring.velScaleY += forceScale * dt
  spring.scaleY += spring.velScaleY * dt

  // Volume preservation: Sx = Sz = 1 / sqrt(Sy)
  const clampedScaleY = Math.max(0.45, Math.min(2.2, spring.scaleY))
  const scaleXZ = 1.0 / Math.sqrt(clampedScaleY)
  spriteRoot.scale.set(scaleXZ, clampedScaleY, scaleXZ)

  // Idle hover floating animation
  const floatSpeed = props.state === 'thinking' ? 5.0 : 2.2
  const floatAmp = props.state === 'thinking' ? 0.22 : 0.12
  const idleFloat = Math.sin(time * floatSpeed) * floatAmp
  spriteRoot.position.y = spring.y + idleFloat

  // Orientation Tilt (Head follow gaze + inertia)
  const tiltFactor = props.state === 'curious' ? 0.75 : 0.45
  spriteRoot.rotation.y = mouse.x * tiltFactor
  spriteRoot.rotation.x = -mouse.y * (tiltFactor * 0.7)
  spriteRoot.rotation.z = -mouse.x * 0.15

  // 3. Eye Microsaccades & Gaze Tracking
  saccadeTimer += dt
  if (saccadeTimer > 1.4 + Math.random() * 1.6) {
    saccadeTimer = 0
    saccadeOffset.x = (Math.random() - 0.5) * 0.06
    saccadeOffset.y = (Math.random() - 0.5) * 0.05
  }

  const gazeX = mouse.x * 0.09 + saccadeOffset.x
  const gazeY = mouse.y * 0.07 + saccadeOffset.y

  if (leftPupil && rightPupil) {
    leftPupil.position.x = gazeX
    leftPupil.position.y = gazeY
    rightPupil.position.x = gazeX
    rightPupil.position.y = gazeY
  }

  // 4. Natural Blinking Animation
  blinkTimer += dt
  if (blinkTimer > 3.8) {
    const blinkProgress = (blinkTimer - 3.8) / 0.16
    if (blinkProgress <= 1.0) {
      const eyeScaleY = Math.abs(Math.sin(blinkProgress * Math.PI - Math.PI / 2))
      eyeGroup.scale.y = Math.max(0.06, eyeScaleY)
    } else {
      eyeGroup.scale.y = 1.0
      blinkTimer = Math.random() * 1.0
    }
  }

  // 5. Ear / Antenna Physics Lag
  const earWiggle = Math.sin(time * 4.0) * 0.15 + (spring.scaleY - 1.0) * 0.4
  if (leftEar && rightEar) {
    leftEar.position.y = 0.85 + earWiggle
    leftEar.rotation.z = Math.sin(time * 3.5) * 0.2 - 0.3
    rightEar.position.y = 0.85 + earWiggle
    rightEar.rotation.z = -Math.sin(time * 3.5) * 0.2 + 0.3
  }

  // 6. Simplex Noise Organic Jelly Deformation
  const posAttr = bodyGeo.attributes.position as THREE.BufferAttribute
  const noiseSpeed = props.state === 'thinking' ? 2.2 : 0.85
  const baseFreq = 1.1
  const strength = props.noiseStrength

  const breathe = Math.sin(time * (props.state === 'thinking' ? 6.0 : 2.8)) * 0.045

  for (let i = 0; i < posAttr.count; i++) {
    const ox = bodyOriginalPos.getX(i)
    const oy = bodyOriginalPos.getY(i)
    const oz = bodyOriginalPos.getZ(i)

    const n = defaultNoise.noise3D(
      ox * baseFreq + time * noiseSpeed,
      oy * baseFreq + time * noiseSpeed,
      oz * baseFreq + time * noiseSpeed
    ) * strength

    const disp = 1.0 + breathe + n
    posAttr.setXYZ(i, ox * disp, oy * disp, oz * disp)
  }
  bodyGeo.computeVertexNormals()
  posAttr.needsUpdate = true
  bodyMat.uniforms.uTime.value = time

  // 7. Core Heartbeat & Pulse
  const pulseSpeed = props.state === 'thinking' ? 12.0 : 4.5
  const heartBeat = 1.0 + Math.sin(time * pulseSpeed) * 0.1 + burstIntensity * 0.3
  coreMesh.scale.setScalar(heartBeat)

  // Decay burst intensity
  if (burstIntensity > 0.001) {
    burstIntensity *= 0.92
  }

  // 8. Particle Swarm & Curl Vector Field Update
  const pPositions = particleGeo.attributes.position.array as Float32Array
  const pCount = particleData.length
  const pSpeedMul = props.state === 'thinking' ? 2.2 : 1.0

  for (let i = 0; i < pCount; i++) {
    const meta = particleData[i]
    meta.theta += meta.speedTheta * dt * pSpeedMul
    meta.phi += meta.speedPhi * dt * pSpeedMul

    // Curl noise perturbation
    const rNoise = defaultNoise.noise2D(meta.theta * 2.0, time * 0.6) * 0.22
    const currentR = meta.baseRadius + rNoise + (spring.scaleY - 1.0) * 0.6 + burstIntensity * 0.8

    pPositions[i * 3] = currentR * Math.sin(meta.phi) * Math.cos(meta.theta)
    pPositions[i * 3 + 1] = currentR * Math.sin(meta.phi) * Math.sin(meta.theta)
    pPositions[i * 3 + 2] = currentR * Math.cos(meta.phi)
  }
  particleGeo.attributes.position.needsUpdate = true

  renderer.render(scene, camera)
}

// --- Public Trigger Methods ---
function triggerBounce(force = 4.2) {
  spring.velY = force
  spring.velScaleY = 1.35 // Stretch vertically
  burstIntensity = 1.0

  // Temporary excited eye widen
  if (eyeGroup) {
    eyeGroup.scale.set(1.25, 1.25, 1.25)
    setTimeout(() => {
      if (eyeGroup) eyeGroup.scale.set(1, 1, 1)
    }, 450)
  }
}

function triggerPulse() {
  burstIntensity = 1.2
}

function setGaze(x: number, y: number) {
  mouse.targetX = x
  mouse.targetY = y
}

defineExpose({
  triggerBounce,
  triggerPulse,
  setGaze
})

// --- Interaction Handlers ---
function onPointerMove(e: PointerEvent) {
  if (!props.interactive || !containerRef.value) return
  const rect = containerRef.value.getBoundingClientRect()
  mouse.targetX = ((e.clientX - rect.left) / rect.width) * 2 - 1
  mouse.targetY = -(((e.clientY - rect.top) / rect.height) * 2 - 1)
  mouse.isInside = true
}

function onPointerLeave() {
  if (!props.interactive) return
  mouse.targetX = 0
  mouse.targetY = 0
  mouse.isInside = false
}

function onPointerDown() {
  if (!props.interactive) return
  triggerBounce()
  emit('click-sprite')
}

// --- Theme and State Watchers ---
function updateThemeColors(themeName: string) {
  const theme = THEMES[themeName] || THEMES.nebula
  if (bodyMat) {
    bodyMat.uniforms.uColorA.value.copy(theme.primary)
    bodyMat.uniforms.uColorB.value.copy(theme.secondary)
    bodyMat.uniforms.uGlowColor.value.copy(theme.core)
  }
  if (coreMesh) {
    (coreMesh.material as THREE.MeshBasicMaterial).color.copy(theme.core)
  }
  if (leftPupil && rightPupil) {
    (leftPupil.material as THREE.MeshBasicMaterial).color.copy(theme.eyes)
    ;(rightPupil.material as THREE.MeshBasicMaterial).color.copy(theme.eyes)
  }
  if (particlePoints) {
    (particlePoints.material as THREE.PointsMaterial).color.copy(theme.particles)
  }
  if (leftEar && rightEar) {
    (leftEar.material as THREE.MeshBasicMaterial).color.copy(theme.secondary)
    ;(rightEar.material as THREE.MeshBasicMaterial).color.copy(theme.secondary)
  }
}

watch(() => props.theme, (newTheme) => {
  updateThemeColors(newTheme)
})

watch(() => props.state, (newState) => {
  if (newState === 'bouncy') {
    triggerBounce()
  } else if (newState === 'thinking') {
    burstIntensity = 0.8
  }
})

// --- Lifecycle Cleanup ---
onMounted(() => {
  initScene()
  setTimeout(() => {
    handleResize()
  }, 100)
  setTimeout(() => {
    handleResize()
  }, 350)
})

onBeforeUnmount(() => {
  if (animFrameId !== null) {
    cancelAnimationFrame(animFrameId)
  }
  if (resizeObserver) {
    resizeObserver.disconnect()
  }

  // Dispose WebGL Geometries and Materials
  bodyGeo?.dispose()
  bodyMat?.dispose()
  particleGeo?.dispose()
  renderer?.dispose()
  scene?.clear()
})
</script>

<style scoped lang="scss">
.aether-sprite-container {
  position: relative;
  display: block;
  user-select: none;
  touch-action: none;
  overflow: visible;

  &.is-interactive {
    cursor: pointer;
  }

  &.mode-mini {
    width: 68px;
    height: 68px;
    display: inline-block;
  }

  &.mode-card {
    width: 100%;
    height: 280px;
    min-height: 200px;
    display: block;
  }

  &.mode-fullscreen {
    width: 100%;
    height: 100%;
    min-height: 480px;
    display: block;
  }

  .aether-canvas {
    width: 100%;
    height: 100%;
    display: block;
    pointer-events: auto;
  }
}
</style>
