(()=>{var U=Object.create;var M=Object.defineProperty;var y=Object.getOwnPropertyDescriptor;var B=Object.getOwnPropertyNames;var D=Object.getPrototypeOf,P=Object.prototype.hasOwnProperty;var F=(i,e)=>()=>{try{return e||i((e={exports:{}}).exports,e),e.exports}catch(o){throw e=0,o}};var z=(i,e,o,r)=>{if(e&&typeof e=="object"||typeof e=="function")for(let a of B(e))!P.call(i,a)&&a!==o&&M(i,a,{get:()=>e[a],enumerable:!(r=y(e,a))||r.enumerable});return i};var T=(i,e,o)=>(o=i!=null?U(D(i)):{},z(e||!i||!i.__esModule?M(o,"default",{value:i,enumerable:!0}):o,i));var c=F((Q,S)=>{S.exports=window.THREE});var t=T(c(),1);var h=T(c(),1),d=class{constructor(){this.isPass=!0,this.enabled=!0,this.needsSwap=!0,this.clear=!1,this.renderToScreen=!1}setSize(){}render(){console.error("THREE.Pass: .render() must be implemented in derived pass.")}dispose(){}},V=new h.OrthographicCamera(-1,1,1,-1,0,1),b=class extends h.BufferGeometry{constructor(){super(),this.setAttribute("position",new h.Float32BufferAttribute([-1,3,0,-1,-1,0,3,-1,0],3)),this.setAttribute("uv",new h.Float32BufferAttribute([0,2,0,0,2,0],2))}},H=new b,v=class{constructor(e){this._mesh=new h.Mesh(H,e)}dispose(){this._mesh.geometry.dispose()}render(e){e.render(this._mesh,V)}get material(){return this._mesh.material}set material(e){this._mesh.material=e}};var p={name:"CopyShader",uniforms:{tDiffuse:{value:null},opacity:{value:1}},vertexShader:`

		varying vec2 vUv;

		void main() {

			vUv = uv;
			gl_Position = projectionMatrix * modelViewMatrix * vec4( position, 1.0 );

		}`,fragmentShader:`

		uniform float opacity;

		uniform sampler2D tDiffuse;

		varying vec2 vUv;

		void main() {

			vec4 texel = texture2D( tDiffuse, vUv );
			gl_FragColor = opacity * texel;


		}`};var C=T(c(),1),w={name:"LuminosityHighPassShader",uniforms:{tDiffuse:{value:null},luminosityThreshold:{value:1},smoothWidth:{value:1},defaultColor:{value:new C.Color(0)},defaultOpacity:{value:0}},vertexShader:`

		varying vec2 vUv;

		void main() {

			vUv = uv;

			gl_Position = projectionMatrix * modelViewMatrix * vec4( position, 1.0 );

		}`,fragmentShader:`

		uniform sampler2D tDiffuse;
		uniform vec3 defaultColor;
		uniform float defaultOpacity;
		uniform float luminosityThreshold;
		uniform float smoothWidth;

		varying vec2 vUv;

		void main() {

			vec4 texel = texture2D( tDiffuse, vUv );

			float v = luminance( texel.xyz );

			vec4 outputColor = vec4( defaultColor.rgb, defaultOpacity );

			float alpha = smoothstep( luminosityThreshold, luminosityThreshold + smoothWidth, v );

			gl_FragColor = mix( outputColor, texel, alpha );

		}`};var f=class i extends d{constructor(e,o=1,r,a){super(),this.strength=o,this.radius=r,this.threshold=a,this.resolution=e!==void 0?new t.Vector2(e.x,e.y):new t.Vector2(256,256),this.clearColor=new t.Color(0,0,0),this.needsSwap=!1,this.renderTargetsHorizontal=[],this.renderTargetsVertical=[],this.nMips=5;let s=Math.round(this.resolution.x/2),n=Math.round(this.resolution.y/2);this.renderTargetBright=new t.WebGLRenderTarget(s,n,{type:t.HalfFloatType}),this.renderTargetBright.texture.name="UnrealBloomPass.bright",this.renderTargetBright.texture.generateMipmaps=!1;for(let u=0;u<this.nMips;u++){let g=new t.WebGLRenderTarget(s,n,{type:t.HalfFloatType});g.texture.name="UnrealBloomPass.h"+u,g.texture.generateMipmaps=!1,this.renderTargetsHorizontal.push(g);let x=new t.WebGLRenderTarget(s,n,{type:t.HalfFloatType});x.texture.name="UnrealBloomPass.v"+u,x.texture.generateMipmaps=!1,this.renderTargetsVertical.push(x),s=Math.round(s/2),n=Math.round(n/2)}let m=w;this.highPassUniforms=t.UniformsUtils.clone(m.uniforms),this.highPassUniforms.luminosityThreshold.value=a,this.highPassUniforms.smoothWidth.value=.01,this.materialHighPassFilter=new t.ShaderMaterial({uniforms:this.highPassUniforms,vertexShader:m.vertexShader,fragmentShader:m.fragmentShader}),this.separableBlurMaterials=[];let l=[3,5,7,9,11];s=Math.round(this.resolution.x/2),n=Math.round(this.resolution.y/2);for(let u=0;u<this.nMips;u++)this.separableBlurMaterials.push(this._getSeparableBlurMaterial(l[u])),this.separableBlurMaterials[u].uniforms.invSize.value=new t.Vector2(1/s,1/n),s=Math.round(s/2),n=Math.round(n/2);this.compositeMaterial=this._getCompositeMaterial(this.nMips),this.compositeMaterial.uniforms.blurTexture1.value=this.renderTargetsVertical[0].texture,this.compositeMaterial.uniforms.blurTexture2.value=this.renderTargetsVertical[1].texture,this.compositeMaterial.uniforms.blurTexture3.value=this.renderTargetsVertical[2].texture,this.compositeMaterial.uniforms.blurTexture4.value=this.renderTargetsVertical[3].texture,this.compositeMaterial.uniforms.blurTexture5.value=this.renderTargetsVertical[4].texture,this.compositeMaterial.uniforms.bloomStrength.value=o,this.compositeMaterial.uniforms.bloomRadius.value=.1;let _=[1,.8,.6,.4,.2];this.compositeMaterial.uniforms.bloomFactors.value=_,this.bloomTintColors=[new t.Vector3(1,1,1),new t.Vector3(1,1,1),new t.Vector3(1,1,1),new t.Vector3(1,1,1),new t.Vector3(1,1,1)],this.compositeMaterial.uniforms.bloomTintColors.value=this.bloomTintColors,this.copyUniforms=t.UniformsUtils.clone(p.uniforms),this.blendMaterial=new t.ShaderMaterial({uniforms:this.copyUniforms,vertexShader:p.vertexShader,fragmentShader:p.fragmentShader,blending:t.AdditiveBlending,depthTest:!1,depthWrite:!1,transparent:!0}),this._oldClearColor=new t.Color,this._oldClearAlpha=1,this._basic=new t.MeshBasicMaterial,this._fsQuad=new v(null)}dispose(){for(let e=0;e<this.renderTargetsHorizontal.length;e++)this.renderTargetsHorizontal[e].dispose();for(let e=0;e<this.renderTargetsVertical.length;e++)this.renderTargetsVertical[e].dispose();this.renderTargetBright.dispose();for(let e=0;e<this.separableBlurMaterials.length;e++)this.separableBlurMaterials[e].dispose();this.compositeMaterial.dispose(),this.blendMaterial.dispose(),this._basic.dispose(),this._fsQuad.dispose()}setSize(e,o){let r=Math.round(e/2),a=Math.round(o/2);this.renderTargetBright.setSize(r,a);for(let s=0;s<this.nMips;s++)this.renderTargetsHorizontal[s].setSize(r,a),this.renderTargetsVertical[s].setSize(r,a),this.separableBlurMaterials[s].uniforms.invSize.value=new t.Vector2(1/r,1/a),r=Math.round(r/2),a=Math.round(a/2)}render(e,o,r,a,s){e.getClearColor(this._oldClearColor),this._oldClearAlpha=e.getClearAlpha();let n=e.autoClear;e.autoClear=!1,e.setClearColor(this.clearColor,0),s&&e.state.buffers.stencil.setTest(!1),this.renderToScreen&&(this._fsQuad.material=this._basic,this._basic.map=r.texture,e.setRenderTarget(null),e.clear(),this._fsQuad.render(e)),this.highPassUniforms.tDiffuse.value=r.texture,this.highPassUniforms.luminosityThreshold.value=this.threshold,this._fsQuad.material=this.materialHighPassFilter,e.setRenderTarget(this.renderTargetBright),e.clear(),this._fsQuad.render(e);let m=this.renderTargetBright;for(let l=0;l<this.nMips;l++)this._fsQuad.material=this.separableBlurMaterials[l],this.separableBlurMaterials[l].uniforms.colorTexture.value=m.texture,this.separableBlurMaterials[l].uniforms.direction.value=i.BlurDirectionX,e.setRenderTarget(this.renderTargetsHorizontal[l]),e.clear(),this._fsQuad.render(e),this.separableBlurMaterials[l].uniforms.colorTexture.value=this.renderTargetsHorizontal[l].texture,this.separableBlurMaterials[l].uniforms.direction.value=i.BlurDirectionY,e.setRenderTarget(this.renderTargetsVertical[l]),e.clear(),this._fsQuad.render(e),m=this.renderTargetsVertical[l];this._fsQuad.material=this.compositeMaterial,this.compositeMaterial.uniforms.bloomStrength.value=this.strength,this.compositeMaterial.uniforms.bloomRadius.value=this.radius,this.compositeMaterial.uniforms.bloomTintColors.value=this.bloomTintColors,e.setRenderTarget(this.renderTargetsHorizontal[0]),e.clear(),this._fsQuad.render(e),this._fsQuad.material=this.blendMaterial,this.copyUniforms.tDiffuse.value=this.renderTargetsHorizontal[0].texture,s&&e.state.buffers.stencil.setTest(!0),this.renderToScreen?(e.setRenderTarget(null),this._fsQuad.render(e)):(e.setRenderTarget(r),this._fsQuad.render(e)),e.setClearColor(this._oldClearColor,this._oldClearAlpha),e.autoClear=n}_getSeparableBlurMaterial(e){let o=[];for(let r=0;r<e;r++)o.push(.39894*Math.exp(-.5*r*r/(e*e))/e);return new t.ShaderMaterial({defines:{KERNEL_RADIUS:e},uniforms:{colorTexture:{value:null},invSize:{value:new t.Vector2(.5,.5)},direction:{value:new t.Vector2(.5,.5)},gaussianCoefficients:{value:o}},vertexShader:`varying vec2 vUv;
				void main() {
					vUv = uv;
					gl_Position = projectionMatrix * modelViewMatrix * vec4( position, 1.0 );
				}`,fragmentShader:`#include <common>
				varying vec2 vUv;
				uniform sampler2D colorTexture;
				uniform vec2 invSize;
				uniform vec2 direction;
				uniform float gaussianCoefficients[KERNEL_RADIUS];

				void main() {
					float weightSum = gaussianCoefficients[0];
					vec3 diffuseSum = texture2D( colorTexture, vUv ).rgb * weightSum;
					for( int i = 1; i < KERNEL_RADIUS; i ++ ) {
						float x = float(i);
						float w = gaussianCoefficients[i];
						vec2 uvOffset = direction * invSize * x;
						vec3 sample1 = texture2D( colorTexture, vUv + uvOffset ).rgb;
						vec3 sample2 = texture2D( colorTexture, vUv - uvOffset ).rgb;
						diffuseSum += (sample1 + sample2) * w;
						weightSum += 2.0 * w;
					}
					gl_FragColor = vec4(diffuseSum/weightSum, 1.0);
				}`})}_getCompositeMaterial(e){return new t.ShaderMaterial({defines:{NUM_MIPS:e},uniforms:{blurTexture1:{value:null},blurTexture2:{value:null},blurTexture3:{value:null},blurTexture4:{value:null},blurTexture5:{value:null},bloomStrength:{value:1},bloomFactors:{value:null},bloomTintColors:{value:null},bloomRadius:{value:0}},vertexShader:`varying vec2 vUv;
				void main() {
					vUv = uv;
					gl_Position = projectionMatrix * modelViewMatrix * vec4( position, 1.0 );
				}`,fragmentShader:`varying vec2 vUv;
				uniform sampler2D blurTexture1;
				uniform sampler2D blurTexture2;
				uniform sampler2D blurTexture3;
				uniform sampler2D blurTexture4;
				uniform sampler2D blurTexture5;
				uniform float bloomStrength;
				uniform float bloomRadius;
				uniform float bloomFactors[NUM_MIPS];
				uniform vec3 bloomTintColors[NUM_MIPS];

				float lerpBloomFactor(const in float factor) {
					float mirrorFactor = 1.2 - factor;
					return mix(factor, mirrorFactor, bloomRadius);
				}

				void main() {
					gl_FragColor = bloomStrength * ( lerpBloomFactor(bloomFactors[0]) * vec4(bloomTintColors[0], 1.0) * texture2D(blurTexture1, vUv) +
						lerpBloomFactor(bloomFactors[1]) * vec4(bloomTintColors[1], 1.0) * texture2D(blurTexture2, vUv) +
						lerpBloomFactor(bloomFactors[2]) * vec4(bloomTintColors[2], 1.0) * texture2D(blurTexture3, vUv) +
						lerpBloomFactor(bloomFactors[3]) * vec4(bloomTintColors[3], 1.0) * texture2D(blurTexture4, vUv) +
						lerpBloomFactor(bloomFactors[4]) * vec4(bloomTintColors[4], 1.0) * texture2D(blurTexture5, vUv) );
				}`})}};f.BlurDirectionX=new t.Vector2(1,0);f.BlurDirectionY=new t.Vector2(0,1);window.UnrealBloomPass=f;})();
