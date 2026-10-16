import { useEffect, useState, useMemo, useRef } from "react";
import * as THREE from "three";
import { IconWallet } from "./icons.jsx";

// ── Three.js Money Rain Engine ──────────────────────────────────────────────
function MoneyRainThree({ images, closing }) {
  const containerRef = useRef(null);
  const closingRef = useRef(closing);
  const engine = useRef({ active: true });

  useEffect(() => { closingRef.current = closing; }, [closing]);

  useEffect(() => {
    if (!containerRef.current) return;
    engine.current.active = true;

    const width = window.innerWidth;
    const height = window.innerHeight;
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 1000);
    camera.position.z = 10;

    const ambientLight = new THREE.AmbientLight(0xffffff, 0.4);
    scene.add(ambientLight);
    const directionalLight = new THREE.DirectionalLight(0xffffff, 1.2);
    directionalLight.position.set(5, 15, 10);
    scene.add(directionalLight);

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.0;
    renderer.domElement.style.opacity = "1";
    containerRef.current.appendChild(renderer.domElement);

    const loader = new THREE.TextureLoader();
    const banknotes = [];
    const clock = new THREE.Clock();

    for (let i = 0; i < 250; i++) {
      const geometry = new THREE.PlaneGeometry(3.5, 1.7, 12, 8);
      const material = new THREE.MeshLambertMaterial({
        color: 0xcccccc,
        side: THREE.DoubleSide,
        transparent: false,
        opacity: 1.0,
        map: null
      });

      const mesh = new THREE.Mesh(geometry, material);
      
      loader.load(images[i % images.length], 
        (tex) => {
          tex.colorSpace = THREE.SRGBColorSpace;
          tex.anisotropy = renderer.capabilities.getMaxAnisotropy();
          tex.magFilter = THREE.LinearFilter;
          tex.minFilter = THREE.LinearMipmapLinearFilter;
          material.map = tex;
          material.needsUpdate = true;
        }
      );

      const state = {
        mesh,
        geometry,
        speed: 0.05 + Math.random() * 0.15,
        x: (Math.random() - 0.5) * 28,
        y: (Math.random() * 50) - 25,
        z: (Math.random() - 0.5) * 18,
        rot: { x: Math.random() * 0.03, y: Math.random() * 0.04 },
        phase: Math.random() * Math.PI * 2
      };
      
      mesh.position.set(state.x, state.y, state.z);
      mesh.rotation.set(Math.random(), Math.random(), Math.random());
      scene.add(mesh);
      banknotes.push(state);
    }

    const run = () => {
      if (!engine.current.active) return;
      
      const delta = clock.getDelta();
      const time = clock.getElapsedTime();
      const deltaMultiplier = delta * 60 || 1;

      if (closingRef.current && renderer.domElement) {
        const currentOp = parseFloat(renderer.domElement.style.opacity) || 0;
        if (currentOp > 0) {
          renderer.domElement.style.opacity = (currentOp - 0.04).toString();
        }
      }

      banknotes.forEach(b => {
        b.y -= b.speed * deltaMultiplier;
        if (b.y < -18) {
          b.y = 18;
          b.x = (Math.random() - 0.5) * 22;
        }
        b.mesh.position.y = b.y;
        b.mesh.position.x += Math.sin(time + b.phase) * 0.02;
        b.mesh.rotation.x += b.rot.x * deltaMultiplier;
        b.mesh.rotation.y += b.rot.y * deltaMultiplier;

        const pos = b.geometry.attributes.position;
        for (let j = 0; j < pos.count; j++) {
          const px = pos.getX(j);
          const bend = Math.sin(time * 4 + px * 1.5 + b.phase) * 0.35;
          pos.setZ(j, bend);
        }
        pos.needsUpdate = true;
      });

      renderer.render(scene, camera);
      requestAnimationFrame(run);
    };

    requestAnimationFrame(run);

    const onResize = () => {
      camera.aspect = window.innerWidth / window.innerHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(window.innerWidth, window.innerHeight);
    };
    window.addEventListener('resize', onResize);

    return () => {
      engine.current.active = false;
      window.removeEventListener('resize', onResize);
      if (containerRef.current && renderer.domElement) {
        containerRef.current.removeChild(renderer.domElement);
      }
      renderer.dispose();
      banknotes.forEach(b => {
        b.geometry.dispose();
        if (b.mesh.material.map) b.mesh.material.map.dispose();
        b.mesh.material.dispose();
      });
    };
  }, [images]);

  return <div ref={containerRef} style={{ position: 'absolute', inset: 0, zIndex: 0, pointerEvents: 'none' }} />;
}

const FUN_FACTS = [
  "The word 'budget' comes from 'bougette', meaning a small leather bag.",
  "Over 80% of all stock market trading is done by algorithmic bots.",
  "If you know the market and know yourself, you need not fear a hundred margin calls.",
  "Bitcoin's creator remains anonymous under the name Satoshi Nakamoto.",
  "Oil is nicknamed 'Black Gold', while Silver is 'The Poor Man's Gold'.",
  "October is one of the peculiarly dangerous months to speculate in stocks.",
  "The supreme art of finance is to subdue the market without fighting.",
  "Silver has the highest electrical and thermal conductivity of any metal.",
  "My investment strategy? Buy high, sell low, cry in the corner.",
  "A stockbroker is someone who invests your money until it's all gone.",
  "The first stock market was created in Amsterdam in 1602.",
  "Gold is so rare that all ever mined would fit in 3 Olympic pools.",
  "Not your keys, not your coins. Always remember the crypto mantra.",
  "In the midst of chaos, there is also opportunity and extreme volatility.",
  "The best time to plant a tree was 20 years ago. The second best time is now.",
  "Compound interest is the eighth wonder of the world.",
  "Bull markets are born on pessimism and grow on skepticism.",
  "The stock market is a device for transferring money from the impatient to the patient.",
  "Opportunities come infrequently. When it rains gold, put out the bucket, not the thimble.",
  "Beware of little expenses; a small leak will sink a great ship.",
  "The most reflective element on the periodic table is Silver.",
  "A wise trader makes many calculations before the opening bell.",
  "Diversification is protection against ignorance.",
  "Price is what you pay. Value is what you get.",
  "Risk comes from not knowing what you're doing.",
  "The market can stay irrational longer than you can stay solvent.",
  "An investment in knowledge pays the best interest.",
  "Don't look for the needle in the haystack. Just buy the haystack.",
  "I'm so poor I can't even pay attention.",
  "Money can't buy happiness, but it's more comfortable to cry in a Ferrari.",
  "To know your enemy, you must become your enemy. To know the chart, you must become the candle.",
  "He who will not economize will have to agonize."
];

export default function IntroScreen({ onFinish }) {
  const [closing, setClosing] = useState(false);
  const [factIndex, setFactIndex] = useState(0);

  useEffect(() => {
    const autoTimer = setTimeout(() => {
      setClosing(true);
      setTimeout(onFinish, 800);
    }, 10000);
    return () => { clearTimeout(autoTimer); };
  }, [onFinish]);

  useEffect(() => {
    const rotationTimer = setTimeout(() => {
      setFactIndex((prev) => (prev + 1) % FUN_FACTS.length);
    }, 2800);
    return () => clearTimeout(rotationTimer);
  }, [factIndex]);

  const billImages = useMemo(() => [
    "/bill/Series_F_10000_yen_front.jpg",
    "/bill/TE-2022-100000-depan.jpg",
    "/bill/The_Europa_series_100_€_obverse_side.jpg",
    "/assets/investments/Investment (1).jpeg",
    "/assets/investments/Investment (2).jpeg",
    "/assets/investments/Investment (3).jpeg",
    "/assets/investments/Investment (4).jpeg",
    "/assets/investments/Investment (5).jpeg",
    "/assets/investments/Investment (6).jpeg",
    "/assets/investments/Investment (7).jpeg",
    "/assets/investments/Investment (8).jpeg",
    "/assets/investments/Investment (9).jpeg"
  ], []);

  const handleManualFinish = () => {
    if (closing) return;
    setClosing(true);
    setTimeout(onFinish, 600);
  };

  return (
    <div 
      className={`intro-overlay ${closing ? "exit" : ""}`} 
      style={{ cursor: "pointer", background: "var(--bg)", overflow: "hidden", pointerEvents: closing ? "none" : "auto" }}
      onClick={handleManualFinish}
    >
      <MoneyRainThree images={billImages} closing={closing} />
      <div className="intro-content" style={{ position: 'relative', zIndex: 10005 }}>
        <div className="intro-logo-outer">
          <div className="intro-logo">
            <IconWallet size={40} color="var(--bg2)" />
          </div>
          <div className="intro-pulse" />
        </div>
        <h1 className="intro-title">Alpha</h1>
        <div className="intro-status" style={{ minHeight: '1.5em' }}>
          <span className="dot" />
          <span key={factIndex} className="fade-in-status">
            {FUN_FACTS[factIndex]}
          </span>
        </div>
        <div style={{ marginTop: 40, fontSize: 10, color: "var(--tx3)", opacity: 0.6, textTransform: "uppercase", letterSpacing: 2 }}>
          Tap to Continue
        </div>
      </div>

      <style>{`
        .fade-in-status {
          display: inline-block;
          animation: fadeInStatus 0.4s ease-out forwards;
        }
        @keyframes fadeInStatus {
          from { opacity: 0; transform: translateY(5px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}
