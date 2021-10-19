/*
    dmakLoader.js and dmak.js

    Adds cancel_prepare to DMAK
*/

;(function () {

	"use strict";

	// Create a safe reference to the DrawMeAKanji object for use below.
	var DmakLoader = function (uri) {
		this.uri = uri;
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
					console.log("Error", msg);
				}
			};

		for (i = 0; i < nbChar; i++) {
			loadSvg(this.uri, i, text.charCodeAt(i).toString(16), callbacks);
		}
	};

	/**
	 * Try to load a SVG file matching the given char code.
	 * @thanks to the incredible work made by KanjiVG
	 * @see: http://kanjivg.tagaini.net
	 */
	function loadSvg(uri, index, charCode, callbacks) {
		var xhr = new XMLHttpRequest(),
			code = ("00000" + charCode).slice(-5);

		// Skip space character
		if(code === "00020" || code === "03000") {
			callbacks.done(index, {
				paths: [],
				texts: []
			});
			return;
		}

		xhr.open("GET", uri + code + ".svg", true);
		xhr.onreadystatechange = function () {
			if (xhr.readyState === 4) {
				if (xhr.status === 200) {
					callbacks.done(index, parseResponse(xhr.response, code));
				} else {
					callbacks.error(xhr.statusText);
				}
			}
		};
		xhr.send();
	}

	/**
	 * Simple parser to extract paths and texts data.
	 */
	function parseResponse(response, code) {
		var data = [],
			dom = new DOMParser().parseFromString(response, "application/xml"),
			texts = dom.querySelectorAll("text"),
			groups = [],
			i;
		
		// Private recursive function to parse DOM content
		function __parse(element) {
            var children = element.childNodes,
                i;

            for(i = 0; i < children.length; i++) {
                if(children[i].tagName === "g") {
                    groups.push(children[i].getAttribute("id"));
                    __parse(children[i]);
                    groups.splice(groups.indexOf(children[i].getAttribute("id")), 1);
                }
                else if(children[i].tagName === "path") {
                    data.push({
                        "path" : children[i].getAttribute("d"),
                        "groups" : groups.slice(0)
                    });
                }
            }
		}

        // Start parsing
		__parse(dom.getElementById("kvg:" + code));

        // And finally add order mark information
		for (i = 0; i < texts.length; i++) {
			data[i].text = {
				"value" : texts[i].textContent,
				"x" : texts[i].getAttribute("transform").split(" ")[4],
				"y" : texts[i].getAttribute("transform").split(" ")[5].replace(")", "")
			};
		}
		
		return data;
	}

	window.DmakLoader = DmakLoader;
}());

/* DMAK */

// ==================================================================
// CHANGES - START - DMAK extended for Migaku
// - dmak.state object and variables
// - numerous callbacks added

/*
*  Draw Me A Kanji - v0.3.1
*  A funny drawer for your Japanese writings
*  http://drawmeakanji.com
*
*  Made by Matthieu Bilbille
*  Under MIT License
*/
;(function () {

	"use strict";

	// Create a safe reference to the DrawMeAKanji object for use below.
	var Dmak = function (text, options) {
		this.text = text;
		// Fix #18 clone `default` to support several instance in parallel
		this.options = assign(clone(Dmak.default), options);
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
			play : [],
			erasing : [],
			drawing : []
		};

		if (!this.options.skipLoad) {
			var loader = new DmakLoader(this.options.uri),
				self = this;

			loader.load(text, function (data) {
				self.prepare(data);

				// Execute custom callback "loaded" here
				self.options.loaded(self.strokes);

				if (self.options.autoplay) {
					self.render();
				}
			});
		}
	};

	// Current version.
	Dmak.VERSION = "0.2.0";

	Dmak.default = {
		uri: "",
		skipLoad: false,
		autoplay: true,
		height: 109,
		width: 109,
		viewBox: {
			x: 0,
			y: 0,
			w: 109,
			h: 109
		},
		step: 0.03,
		element: "draw",
		stroke: {
			animated : {
				drawing : true,
				erasing : true
			},
			order: {
				visible: false,
				attr: {
					"font-size": "8",
					"fill": "#999999"
				}
			},
			attr: {
				"active": "#BF0000",
				// may use the keyword "random" here for random color
				"stroke": "#2C2C2C",
				"stroke-width": 4,
				"stroke-linecap": "round",
				"stroke-linejoin": "round"
			}
		},
		grid: {
			show: true,
			attr: {
				"stroke": "#CCCCCC",
				"stroke-width": 0.5,
				"stroke-dasharray": "--"
			}
		},

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
		erase: function (end, callbackOverride) {
			var finishedErasingCallback = this.options.finishedErasing;

			// Cannot have two rendering process for the same draw. Keep it cool.
			if (this.timeouts.play.length) {
				return false;
			}

			// Don't go behind the beginning.
			if (this.pointer <= 0) {
				return false;
			}

			if (typeof end === "undefined") {
				end = 0;
			}

			dmak.state.isErasing = true;

			var longestEraseDuration = this.strokes[this.pointer - 1].duration;

			do {
				this.pointer--;

				var strokeNum = this.pointer;
				var stroke = this.strokes[strokeNum];
				var strokeDuration = stroke.duration;

				eraseStroke(stroke, this.timeouts.erasing, this.options);

				if (strokeDuration > longestEraseDuration) {
					longestEraseDuration = strokeDuration;
				}

				// Execute custom callback "startedErasing"
				this.options.startedErasing(strokeNum);
			} while (this.pointer > end);

			// Execute custom callback "finishedErasing"
			// (setTimeout according to the longest stroke duration)
			setTimeout(function() {
				dmak.state.isErasing = false;

				// Callback overrides facilitates codesharing with the `replay` funciton
				if (callbackOverride) {
					callbackOverride(end);
				} else {
					finishedErasingCallback(end);
				}
			}, longestEraseDuration);
		},

		/**
		* All the magic happens here.
		*/
		render: function (end, simultaneous, that) {
			// Normalise `this` for when `render` is invoked from within other functions
			// (e.g. in the `replay` function)
			that = that || this;

			var startedDrawingCallback = that.options.startedDrawing,
					finishedDrawingCallback = that.options.finishedDrawing;

			// Cannot have two rendering process for
			// the same draw. Keep it cool.
			if (that.timeouts.play.length) {
				return false;
			}

			if (typeof end === "undefined") {
				end = that.strokes.length;
			} else if (end > that.strokes.length) {
				return false;
			}

			dmak.state.isRendering = true;
			dmak.state.wasRenderingSimultaneous = false;
			dmak.state.wasRenderingSequential = false;

			if (end - that.pointer > 2) {
				if (simultaneous) {
					dmak.state.isRenderingSimultaneous = true;
				} else {
					dmak.state.isRenderingSequential = true;
				}
			}

			var cb = function (context) {
					var strokeNum = context.pointer,
							stroke = context.strokes[strokeNum],
							strokeDuration = stroke && stroke.duration;

					if (!stroke) return;

					dmak.state.renderCount += 1;

					// Execute custom callback "startedDrawing"
					startedDrawingCallback(strokeNum + 1);

					drawStroke(
						context.papers[context.strokes[strokeNum].char],
						context.strokes[strokeNum],
						context.timeouts.drawing,
						context.options
					);

					var isLastStroke = strokeNum + 1 === end;

					setTimeout(function() {
						var pauseButtonHasBeenHit = dmak.timeouts.play.length === 0

						dmak.state.renderCount -= 1;
						dmak.state.isRendering = dmak.state.renderCount !== 0;

						// Execute custom callback "finishedDrawing"
						// Check when a stroke finishes, whether it was the last one,
						// or whether the pause button was hit and drawing aborted
						if (isLastStroke || pauseButtonHasBeenHit) {

							if (dmak.state.isRenderingSequential) {
								dmak.state.wasRenderingSequential = true;
								dmak.state.isRenderingSequential = false;
							}

							finishedDrawingCallback(strokeNum + 1);
						}
					}, strokeDuration);

					context.pointer++;
					context.timeouts.play.shift();
				},
				delay = 0,
				i;

			// Before drawing clear any remaining erasing timeouts
			for (i = 0; i < that.timeouts.erasing.length; i++) {
				window.clearTimeout(that.timeouts.erasing[i]);
				that.timeouts.erasing = [];
			}

			// Draw strokes simultaneously
			if (simultaneous) {
				var initialStroke = that.strokes[0],
						// Initial value only; overridden in loop below
						longestStrokeDuration = initialStroke && initialStroke.duration;

				do {
					var strokeNum = that.pointer,
							stroke = that.strokes[strokeNum],
							strokeDuration = stroke && stroke.duration;

					if (!stroke) continue;

					dmak.state.renderCount += 1;

					drawStroke(
						that.papers[stroke.char],
						stroke,
						that.timeouts.drawing,
						that.options
					);

					// Execute custom callback "finishedDrawing" after final stroke duration
					if (strokeDuration > longestStrokeDuration) {
						longestStrokeDuration = strokeDuration;
					}

					if (that.pointer + 1 < end) {
						setTimeout(function() {
							dmak.state.renderCount -= 1;
							dmak.state.isRendering = dmak.state.renderCount !== 0;
						}, strokeDuration);
					}

					that.pointer++;
				} while (that.pointer < end);

				// Execute custom callback "startedDrawing"
				// This is fired after the do-while loop so that the
				// dmak.timeouts.play array is fully populated
				startedDrawingCallback(end);

				// Execute custom callback "finishedDrawing"
				// (setTimeout according to the longest stroke duration)
				setTimeout(function() {
					dmak.state.renderCount = 0;
					dmak.state.isRendering = false;

					if (dmak.state.isRenderingSimultaneous) {
						dmak.state.wasRenderingSimultaneous = true;
						dmak.state.isRenderingSimultaneous = false;
					}

					finishedDrawingCallback(strokeNum);
				}, longestStrokeDuration);

			// Else draw strokes one at a time
			} else {
				for (i = that.pointer; i < end; i++) {
					if (!that.options.stroke.animated.drawing || delay <= 0) {
						cb(this);
					} else {
						that.timeouts.play.push(setTimeout(cb, delay, this));
					}
					delay += that.strokes[i].duration;
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
		replay: function() {
			var that = this;
			this.erase(0, function() {
				that.render(that.strokes.length, false, that);
			});
		},

		/**
		* Wrap the erase function to remove the x last strokes.
		*/
		eraseLastStrokes: function (nbStrokes) {
			this.erase(this.pointer - nbStrokes);
		},

		/**
		* Wrap the render function to render the x next strokes.
		*/
		renderNextStrokes: function (nbStrokes) {
			this.render(this.pointer + nbStrokes);
		}

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
					"char": i,
					"length": length,
					"duration": length * options.step * 1000,
					"path": data[i][j].path,
					"groups" : data[i][j].groups,
					"text": data[i][j].text,
					"object": {
						"path" : null,
						"text": null
					}
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
			paper = new Raphael(options.element, options.width + "px", options.height + "px");
			paper.setViewBox(options.viewBox.x, options.viewBox.y, options.viewBox.w, options.viewBox.h);
			paper.canvas.setAttribute("class", "dmak-svg");
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
			papers[i].path("M" + (options.viewBox.w / 2) + ",0 L" + (options.viewBox.w / 2) + "," + options.viewBox.h).attr(options.grid.attr);
			papers[i].path("M0," + (options.viewBox.h / 2) + " L" + options.viewBox.w + "," + (options.viewBox.h / 2)).attr(options.grid.attr);
		}
	}

	/**
	* Remove a single stroke ; deletion can be animated if set as so.
	*/
	function eraseStroke(stroke, timeouts, options) {
		// In some cases the text object may be null:
		//  - Stroke order display disabled
		//  - Stroke already deleted
		if (stroke.object.text !== null) {
			stroke.object.text.remove();
		}

		var cb = function() {
			stroke.object.path.remove();

			// Finally properly prepare the object variable
			stroke.object = {
				"path" : null,
				"text" : null
			};

			timeouts.shift();
		};

		if (options.stroke.animated.erasing) {
			stroke.object.path.node.style.stroke = options.stroke.attr.active;
			timeouts.push(animateStroke(stroke, -1, options, cb));
		}
		else {
			cb();
		}
	}

	/**
	* Draw a single stroke ; drawing can be animated if set as so.
	*/
	function drawStroke(paper, stroke, timeouts, options) {
		var cb = function() {

			// The stroke object may have been already erased when we reach this timeout
			if (stroke.object.path === null) {
				return;
			}

			var color = options.stroke.attr.stroke;
			if(options.stroke.attr.stroke === "random") {
				color = Raphael.getColor();
			}

			// Revert back to the default color.
			stroke.object.path.node.style.stroke = color;
			stroke.object.path.node.style.transition = stroke.object.path.node.style.WebkitTransition = "stroke 400ms ease";

			timeouts.shift();
		};

		stroke.object.path = paper.path(stroke.path);
		stroke.object.path.attr(options.stroke.attr);

		if (options.stroke.order.visible) {
			showStrokeOrder(paper, stroke, options);
		}

		if (options.stroke.animated.drawing) {
			animateStroke(stroke, 1, options, cb);
		}
		else {
			cb();
		}
	}

	/**
	* Draw a single next to
	*/
	function showStrokeOrder(paper, stroke, options) {
		stroke.object.text = paper.text(stroke.text.x, stroke.text.y, stroke.text.value);
		stroke.object.text.attr(options.stroke.order.attr);
	}

	/**
	* Animate stroke drawing.
	* Based on the great article wrote by Jake Archibald
	* http://jakearchibald.com/2013/animated-line-drawing-svg/
	*/
	function animateStroke(stroke, direction, options, callback) {
		stroke.object.path.attr({"stroke": options.stroke.attr.active});
		stroke.object.path.node.style.transition = stroke.object.path.node.style.WebkitTransition = "none";

		// Set up the starting positions
		stroke.object.path.node.style.strokeDasharray = stroke.length + " " + stroke.length;
		stroke.object.path.node.style.strokeDashoffset = (direction > 0) ? stroke.length : 0;

		// Trigger a layout so styles are calculated & the browser
		// picks up the starting position before animating
		stroke.object.path.node.getBoundingClientRect();
		stroke.object.path.node.style.transition = stroke.object.path.node.style.WebkitTransition = "stroke-dashoffset " + stroke.duration + "ms ease";

		// Go!
		stroke.object.path.node.style.strokeDashoffset = (direction > 0) ? "0" : stroke.length;

		// Execute the callback once the animation is done
		// and return the timeout id.
		return setTimeout(callback, stroke.duration);
	}

	/**
	* Helper function to clone an object
	*/
	function clone(object) {
		if (object === null || typeof object !== "object") {
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
			throw new Error("Missing arguments in assign function");
		}

		for (var key in source) {
			if (replacement.hasOwnProperty(key)) {
				source[key] = (typeof replacement[key] === "object") ? assign(source[key], replacement[key]) : replacement[key];
			}
		}
		return source;
	}

	window.Dmak = Dmak;
}());

;(function () {

	"use strict";

	// Create a safe reference to the DrawMeAKanji object for use below.
	var DmakLoader = function (uri) {
		this.uri = uri;
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
					console.log("Error", msg);
				}
			};

		for (i = 0; i < nbChar; i++) {
			loadSvg(this.uri, i, text.charCodeAt(i).toString(16), callbacks);
		}
	};

	/**
	* Try to load a SVG file matching the given char code.
	* @thanks to the incredible work made by KanjiVG
	* @see: http://kanjivg.tagaini.net
	*/
	function loadSvg(uri, index, charCode, callbacks) {
		var xhr = new XMLHttpRequest(),
			code = ("00000" + charCode).slice(-5);

		// Skip space character
		if(code === "00020" || code === "03000") {
			callbacks.done(index, {
				paths: [],
				texts: []
			});
			return;
		}

		xhr.open("GET", uri + code + ".svg", true);
		xhr.onreadystatechange = function () {
			if (xhr.readyState === 4) {
				if (xhr.status === 200) {
					callbacks.done(index, parseResponse(xhr.response, code));
				} else {
					callbacks.error(xhr.statusText);
				}
			}
		};
		xhr.send();
	}

	/**
	* Simple parser to extract paths and texts data.
	*/
	function parseResponse(response, code) {
		var data = [],
			dom = new DOMParser().parseFromString(response, "application/xml"),
			texts = dom.querySelectorAll("text"),
			groups = [],
			i;

		// Private recursive function to parse DOM content
		function __parse(element) {
						var children = element.childNodes,
								i;

						for(i = 0; i < children.length; i++) {
								if(children[i].tagName === "g") {
										groups.push(children[i].getAttribute("id"));
										__parse(children[i]);
										groups.splice(groups.indexOf(children[i].getAttribute("id")), 1);
								}
								else if(children[i].tagName === "path") {
										data.push({
												"path" : children[i].getAttribute("d"),
												"groups" : groups.slice(0)
										});
								}
						}
		}

				// Start parsing
		__parse(dom.getElementById("kvg:" + code));

				// And finally add order mark information
		for (i = 0; i < texts.length; i++) {
			data[i].text = {
				"value" : texts[i].textContent,
				"x" : texts[i].getAttribute("transform").split(" ")[4],
				"y" : texts[i].getAttribute("transform").split(" ")[5].replace(")", "")
			};
		}

		return data;
	}

	window.DmakLoader = DmakLoader;
}());

// CHANGES - END - DMAK extended for Migaku
// ==================================================================