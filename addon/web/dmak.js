/* ==================================================================
CHANGES - START - DMAK extended for Migaku
- @version v0.18.1

Changes:
- state object and variables
- numerous callbacks added
- option to preload svg data
================================================================== */

/*
	*  Draw Me A Kanji - v0.3.1
	*  A funny drawer for your Japanese writings
	*  http://drawmeakanji.com
	*
	*  Made by Matthieu Bilbille
	*  Under MIT License
	*/ (function () {
	'use strict';

	// Create a safe reference to the DrawMeAKanji object for use below.
	var Dmak = function (text, options) {
		this.text = text;
		// Fix #18 clone `default` to support several instance in parallel
		this.options = assign(clone(Dmak.default), options);
		this.options.preload_svgs =
			options.preload_svgs || Dmak.default.preload_svgs;
		this.strokes = [];
		this.papers = [];
		this.pointer = 0;
		this.state = {
			isErasing: false,
			renderCount: 0,
			isRendering: false,
			isRenderingSequential: false,
			isRenderingSimultaneous: false,
			wasRenderingSequential: false,
			wasRenderingSimultaneous: false,
		};
		this.timeouts = {
			play: [],
			erasing: [],
			drawing: [],
		};

		if (!this.options.skipLoad) {
			var loader = new DmakLoader(
					this.options.uri,
					this.options.preload_svgs,
				),
				self = this;

			loader.load(text, function (data) {
				self.prepare(data);

				// Execute custom callback "loaded" here
				self.options.loaded(self, self.strokes);

				if (self.options.autoplay) {
					self.render();
				}
			});
		}
	};

	// Current version.
	Dmak.VERSION = '0.2.0';

	Dmak.default = {
		uri: '',
		skipLoad: false,
		autoplay: true,
		height: 109,
		width: 109,
		viewBox: {
			x: 0,
			y: 0,
			w: 109,
			h: 109,
		},
		step: 0.03,
		element: 'draw',
		stroke: {
			animated: {
				drawing: true,
				erasing: true,
			},
			order: {
				visible: false,
				attr: {
					'font-size': '8',
					'fill': '#999999',
				},
			},
			attr: {
				'active': '#BF0000',
				// may use the keyword "random" here for random color
				'stroke': '#2C2C2C',
				'stroke-width': 4,
				'stroke-linecap': 'round',
				'stroke-linejoin': 'round',
			},
		},
		grid: {
			show: true,
			attr: {
				'stroke': '#CCCCCC',
				'stroke-width': 0.5,
				'stroke-dasharray': '--',
			},
		},
		preload_svgs: {},

		// callbacks
		loaded: function () {},
		startedErasing: function () {},
		finishedErasing: function () {},
		startedDrawing: function () {},
		finishedDrawing: function () {},
	};

	Dmak.fn = Dmak.prototype = {
		/**
		 * Prepare kanjis and papers for rendering.
		 */
		prepare: function (data) {
			this.strokes = preprocessStrokes(data, this.options);
			this.papers = giveBirthToRaphael(data.length, this.options);
			if (this.options.grid.show) {
				showGrid(this.papers, this.options);
			}
		},

		/**
		 * Clean all strokes on papers.
		 */
		erase: function (end, callbackOverride, instant = false) {
			var self = this;

			var finishedErasingCallback = self.options.finishedErasing;

			// Cannot have two rendering process for the same draw. Keep it cool.
			if (self.timeouts.play.length) {
				return false;
			}

			// Don't go behind the beginning.
			if (self.pointer <= 0) {
				return false;
			}

			if (typeof end === 'undefined') {
				end = 0;
			}

			self.state.isErasing = true;

			var longestEraseDuration = self.strokes[self.pointer - 1].duration;

			do {
				self.pointer--;

				var strokeNum = self.pointer;
				var stroke = self.strokes[strokeNum];
				var strokeDuration = stroke.duration;

				eraseStroke(stroke, self.timeouts.erasing, self.options, instant);

				if (strokeDuration > longestEraseDuration) {
					longestEraseDuration = strokeDuration;
				}

				// Execute custom callback "startedErasing"
				self.options.startedErasing(self, strokeNum);
			} while (self.pointer > end);

			// Execute custom callback "finishedErasing"
			// (setTimeout according to the longest stroke duration)
			setTimeout(
				function () {
					self.state.isErasing = false;

					// Callback overrides facilitates codesharing with the `replay` funciton
					if (callbackOverride) {
						callbackOverride(end);
					} else {
						finishedErasingCallback(self, end);
					}
				},
				instant ? 0 : longestEraseDuration,
			);
		},

		/**
		 * All the magic happens here.
		 */
		render: function (end, simultaneous, instant = false) {
			self = this;

			var startedDrawingCallback = self.options.startedDrawing,
				finishedDrawingCallback = self.options.finishedDrawing;

			// Cannot have two rendering process for
			// the same draw. Keep it cool.
			if (self.timeouts.play.length) {
				return false;
			}

			if (typeof end === 'undefined') {
				end = self.strokes.length;
			} else if (end > self.strokes.length) {
				return false;
			}

			self.state.isRendering = true;
			self.state.wasRenderingSimultaneous = false;
			self.state.wasRenderingSequential = false;

			if (end - self.pointer > 2) {
				if (simultaneous) {
					self.state.isRenderingSimultaneous = true;
				} else {
					self.state.isRenderingSequential = true;
				}
			}

			var cb = function () {
					var strokeNum = self.pointer,
						stroke = self.strokes[strokeNum],
						strokeDuration = stroke && stroke.duration;

					if (!stroke) return;

					self.state.renderCount += 1;

					// Execute custom callback "startedDrawing"
					startedDrawingCallback(self, strokeNum + 1);

					drawStroke(
						self.papers[self.strokes[strokeNum].char],
						self.strokes[strokeNum],
						self.timeouts.drawing,
						self.options,
					);

					var isLastStroke = strokeNum + 1 === end;

					setTimeout(function () {
						var pauseButtonHasBeenHit = self.timeouts.play.length === 0;

						self.state.renderCount -= 1;
						self.state.isRendering = self.state.renderCount !== 0;

						// Execute custom callback "finishedDrawing"
						// Check when a stroke finishes, whether it was the last one,
						// or whether the pause button was hit and drawing aborted
						if (isLastStroke || pauseButtonHasBeenHit) {
							if (self.state.isRenderingSequential) {
								self.state.wasRenderingSequential = true;
								self.state.isRenderingSequential = false;
							}

							finishedDrawingCallback(self, strokeNum + 1);
						}
					}, strokeDuration);

					self.pointer++;
					self.timeouts.play.shift();
				},
				delay = 0,
				i;

			// Before drawing clear any remaining erasing timeouts
			for (i = 0; i < self.timeouts.erasing.length; i++) {
				window.clearTimeout(self.timeouts.erasing[i]);
				self.timeouts.erasing = [];
			}

			// Draw strokes simultaneously
			if (simultaneous) {
				var initialStroke = self.strokes[0],
					// Initial value only; overridden in loop below
					longestStrokeDuration = initialStroke && initialStroke.duration;

				do {
					var strokeNum = self.pointer,
						stroke = self.strokes[strokeNum],
						strokeDuration = stroke && stroke.duration;

					if (!stroke) continue;

					self.state.renderCount += 1;

					drawStroke(
						self.papers[stroke.char],
						stroke,
						self.timeouts.drawing,
						self.options,
						instant,
					);

					// Execute custom callback "finishedDrawing" after final stroke duration
					if (strokeDuration > longestStrokeDuration) {
						longestStrokeDuration = strokeDuration;
					}

					if (self.pointer + 1 < end) {
						setTimeout(function () {
							self.state.renderCount -= 1;
							self.state.isRendering = self.state.renderCount !== 0;
						}, strokeDuration);
					}

					self.pointer++;
				} while (self.pointer < end);

				// Execute custom callback "startedDrawing"
				// This is fired after the do-while loop so that the
				// self.timeouts.play array is fully populated
				startedDrawingCallback(self, end);

				// Execute custom callback "finishedDrawing"
				// (setTimeout according to the longest stroke duration)
				setTimeout(
					function () {
						self.state.renderCount = 0;
						self.state.isRendering = false;

						if (self.state.isRenderingSimultaneous) {
							self.state.wasRenderingSimultaneous = true;
							self.state.isRenderingSimultaneous = false;
						}

						finishedDrawingCallback(self, strokeNum);
					},
					instant ? 0 : longestStrokeDuration,
				);

				// Else draw strokes one at a time
			} else {
				for (i = self.pointer; i < end; i++) {
					if (!self.options.stroke.animated.drawing || delay <= 0) {
						cb();
					} else {
						self.timeouts.play.push(setTimeout(cb, delay));
					}
					delay += self.strokes[i].duration;
				}
			}
		},

		/**
		 * Pause rendering
		 */
		pause: function () {
			for (var i = 0; i < this.timeouts.play.length; i++) {
				window.clearTimeout(this.timeouts.play[i]);
			}
			this.timeouts.play = [];

			// Pause can only occur during sequential rendering
			this.state.wasRenderingSequential = true;
		},

		/**
		 * Fully erase, then autoplay render.
		 */
		replay: function () {
			var self = this;
			this.erase(
				0,
				function () {
					self.render(self.strokes.length, false);
				},
				true,
			);
		},

		/**
		 * Wrap the erase function to remove the x last strokes.
		 */
		eraseLastStrokes: function (nbStrokes, instant = false) {
			this.erase(this.pointer - nbStrokes, undefined, instant);
		},

		/**
		 * Wrap the render function to render the x next strokes.
		 */
		renderNextStrokes: function (nbStrokes, instant = false) {
			this.render(this.pointer + nbStrokes, false, instant);
		},
	};

	// HELPERS

	/**
	 * Flattens the array of strokes ; 3D > 2D and does some preprocessing while
	 * looping through all the strokes:
	 *  - Maps to a character index
	 *  - Calculates path length
	 */
	function preprocessStrokes(data, options) {
		var strokes = [],
			stroke,
			length,
			i,
			j;

		for (i = 0; i < data.length; i++) {
			for (j = 0; j < data[i].length; j++) {
				length = Raphael.getTotalLength(data[i][j].path);
				stroke = {
					char: i,
					length: length,
					duration: length * options.step * 1000,
					path: data[i][j].path,
					groups: data[i][j].groups,
					text: data[i][j].text,
					object: {
						path: null,
						text: null,
					},
				};
				strokes.push(stroke);
			}
		}

		return strokes;
	}

	/**
	 * Init Raphael paper objects
	 */
	function giveBirthToRaphael(nbChar, options) {
		var papers = [],
			paper,
			i;

		for (i = 0; i < nbChar; i++) {
			paper = new Raphael(
				options.element,
				options.width + 'px',
				options.height + 'px',
			);
			paper.setViewBox(
				options.viewBox.x,
				options.viewBox.y,
				options.viewBox.w,
				options.viewBox.h,
			);
			paper.canvas.setAttribute('class', 'dmak-svg');
			papers.push(paper);
		}
		return papers.reverse();
	}

	/**
	 * Draw the background grid
	 */
	function showGrid(papers, options) {
		var i;

		for (i = 0; i < papers.length; i++) {
			papers[i]
				.path(
					'M' +
						options.viewBox.w / 2 +
						',0 L' +
						options.viewBox.w / 2 +
						',' +
						options.viewBox.h,
				)
				.attr(options.grid.attr);
			papers[i]
				.path(
					'M0,' +
						options.viewBox.h / 2 +
						' L' +
						options.viewBox.w +
						',' +
						options.viewBox.h / 2,
				)
				.attr(options.grid.attr);
		}
	}

	/**
	 * Remove a single stroke ; deletion can be animated if set as so.
	 */
	function eraseStroke(stroke, timeouts, options, instant = false) {
		// In some cases the text object may be null:
		//  - Stroke order display disabled
		//  - Stroke already deleted
		if (stroke.object.text !== null) {
			stroke.object.text.remove();
		}

		var cb = function () {
			stroke.object.path.remove();

			// Finally properly prepare the object variable
			stroke.object = {
				path: null,
				text: null,
			};

			timeouts.shift();
		};

		if (options.stroke.animated.erasing && !instant) {
			stroke.object.path.node.style.stroke = options.stroke.attr.active;
			timeouts.push(animateStroke(stroke, -1, options, cb));
		} else {
			cb();
		}
	}

	/**
	 * Draw a single stroke ; drawing can be animated if set as so.
	 */
	function drawStroke(paper, stroke, timeouts, options, instant = false) {
		var cb = function () {
			// The stroke object may have been already erased when we reach this timeout
			if (stroke.object.path === null) {
				return;
			}

			var color = options.stroke.attr.stroke;
			if (options.stroke.attr.stroke === 'random') {
				color = Raphael.getColor();
			}

			// Revert back to the default color.
			stroke.object.path.node.style.stroke = color;
			stroke.object.path.node.style.transition =
				stroke.object.path.node.style.WebkitTransition = 'stroke 400ms ease';

			timeouts.shift();
		};

		stroke.object.path = paper.path(stroke.path);
		stroke.object.path.attr(options.stroke.attr);

		if (options.stroke.order.visible) {
			showStrokeOrder(paper, stroke, options);
		}

		if (options.stroke.animated.drawing && !instant) {
			animateStroke(stroke, 1, options, cb);
		} else {
			cb();
		}
	}

	/**
	 * Draw a single next to
	 */
	function showStrokeOrder(paper, stroke, options) {
		stroke.object.text = paper.text(
			stroke.text.x,
			stroke.text.y,
			stroke.text.value,
		);
		stroke.object.text.attr(options.stroke.order.attr);
	}

	/**
	 * Animate stroke drawing.
	 * Based on the great article wrote by Jake Archibald
	 * http://jakearchibald.com/2013/animated-line-drawing-svg/
	 */
	function animateStroke(stroke, direction, options, callback) {
		stroke.object.path.attr({ stroke: options.stroke.attr.active });
		stroke.object.path.node.style.transition =
			stroke.object.path.node.style.WebkitTransition = 'none';

		// Set up the starting positions
		stroke.object.path.node.style.strokeDasharray =
			stroke.length + ' ' + stroke.length;
		stroke.object.path.node.style.strokeDashoffset =
			direction > 0 ? stroke.length : 0;

		// Trigger a layout so styles are calculated & the browser
		// picks up the starting position before animating
		stroke.object.path.node.getBoundingClientRect();
		stroke.object.path.node.style.transition =
			stroke.object.path.node.style.WebkitTransition =
				'stroke-dashoffset ' + stroke.duration + 'ms ease';

		// Go!
		stroke.object.path.node.style.strokeDashoffset =
			direction > 0 ? '0' : stroke.length;

		// Execute the callback once the animation is done
		// and return the timeout id.
		return setTimeout(callback, stroke.duration);
	}

	/**
	 * Helper function to clone an object
	 */
	function clone(object) {
		if (object === null || typeof object !== 'object') {
			return object;
		}

		var temp = object.constructor(); // give temp the original object's constructor
		for (var key in object) {
			temp[key] = clone(object[key]);
		}

		return temp;
	}

	/**
	 * Helper function to copy own properties over to the destination object.
	 */
	function assign(source, replacement) {
		if (arguments.length !== 2) {
			throw new Error('Missing arguments in assign function');
		}

		for (var key in source) {
			if (replacement.hasOwnProperty(key)) {
				source[key] =
					typeof replacement[key] === 'object'
						? assign(source[key], replacement[key])
						: replacement[key];
			}
		}
		return source;
	}

	window.Dmak = Dmak;
})();
(function () {
	'use strict';

	// Create a safe reference to the DrawMeAKanji object for use below.
	var DmakLoader = function (uri, preload_svgs = {}) {
		this.uri = uri;
		this.preload_svgs = preload_svgs;
	};

	/**
	 * Gather SVG data information for a given set of characters.
	 * By default this action is done while instanciating the Word
	 * object, but it can be skipped, see above
	 */
	DmakLoader.prototype.load = function (text, callback) {
		var paths = [],
			nbChar = text.length,
			done = 0,
			i,
			callbacks = {
				done: function (index, data) {
					paths[index] = data;
					done++;
					if (done === nbChar) {
						callback(paths);
					}
				},
				error: function (msg) {
					console.log('Error', msg);
				},
			};

		for (i = 0; i < nbChar; i++) {
			this.loadSvg(i, text[i], callbacks);
		}
	};

	/**
	 * Try to load a SVG file matching the given char code.
	 * @thanks to the incredible work made by KanjiVG
	 * @see: http://kanjivg.tagaini.net
	 */
	DmakLoader.prototype.loadSvg = function (index, char, callbacks) {
		var charCode = char.charCodeAt(0).toString(16),
			code = ('00000' + charCode).slice(-5),
			preload_svg_data = this.preload_svgs[char];

		if (preload_svg_data) {
			try {
				callbacks.done(index, parseResponse(preload_svg_data, code));
			} catch (e) {
				callbacks.error(e.toString());
			}
			return;
		}

		var xhr = new XMLHttpRequest();

		// Skip space character
		if (code === '00020' || code === '03000') {
			callbacks.done(index, {
				paths: [],
				texts: [],
			});
			return;
		}

		xhr.open('GET', this.uri + code + '.svg', true);
		xhr.onreadystatechange = function () {
			if (xhr.readyState === 4) {
				if (xhr.status === 200) {
					try {
						callbacks.done(index, parseResponse(xhr.response, code));
					} catch (e) {
						callbacks.error(e.toString());
					}
				} else {
					callbacks.error(xhr.statusText);
				}
			}
		};
		xhr.send();
	};

	/**
	 * Simple parser to extract paths and texts data.
	 */
	function parseResponse(response, code) {
		// Prepend XML and SVG headers if required
		if (!response.startsWith('<?xml')) {
			const xml_header = '<?xml version="1.0" encoding="UTF-8"?>\n';
			const svg_header =
				'<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.0//EN" "http://www.w3.org/TR/2001/REC-SVG-20010904/DTD/svg10.dtd" [\n' +
				'<!ATTLIST g\n' +
				'xmlns:kvg CDATA #FIXED "http://kanjivg.tagaini.net"\n' +
				'kvg:element CDATA #IMPLIED\n' +
				'kvg:variant CDATA #IMPLIED\n' +
				'kvg:partial CDATA #IMPLIED\n' +
				'kvg:original CDATA #IMPLIED\n' +
				'kvg:part CDATA #IMPLIED\n' +
				'kvg:number CDATA #IMPLIED\n' +
				'kvg:tradForm CDATA #IMPLIED\n' +
				'kvg:radicalForm CDATA #IMPLIED\n' +
				'kvg:position CDATA #IMPLIED\n' +
				'kvg:radical CDATA #IMPLIED\n' +
				'kvg:phon CDATA #IMPLIED >\n' +
				'<!ATTLIST path\n' +
				'xmlns:kvg CDATA #FIXED "http://kanjivg.tagaini.net"\n' +
				'kvg:type CDATA #IMPLIED >\n' +
				']>\n';

			response = xml_header + svg_header + response;
		}

		var data = [],
			dom = new DOMParser().parseFromString(response, 'application/xml'),
			texts = dom.querySelectorAll('text'),
			groups = [],
			i;

		// Private recursive function to parse DOM content
		function __parse(element) {
			var children = element.childNodes,
				i;

			for (i = 0; i < children.length; i++) {
				if (children[i].tagName === 'g') {
					groups.push(children[i].getAttribute('id'));
					__parse(children[i]);
					groups.splice(groups.indexOf(children[i].getAttribute('id')), 1);
				} else if (children[i].tagName === 'path') {
					data.push({
						path: children[i].getAttribute('d'),
						groups: groups.slice(0),
					});
				}
			}
		}

		// Start parsing
		__parse(dom.getElementById('kvg:' + code));

		// And finally add order mark information
		for (i = 0; i < texts.length; i++) {
			data[i].text = {
				value: texts[i].textContent,
				x: texts[i].getAttribute('transform').split(' ')[4],
				y: texts[i].getAttribute('transform').split(' ')[5].replace(')', ''),
			};
		}

		return data;
	}

	window.DmakLoader = DmakLoader;
})();

// CHANGES - END - DMAK extended for Migaku
// ==================================================================
