import {
  Search,
  Bell,
  UserCircle
} from "lucide-react";


function Navbar(){

  return (

    <header
      className="
        h-16
        border-b
        border-slate-800
        bg-slate-950
        flex
        items-center
        justify-between
        px-6
        text-white
      "
    >


      {/* Search */}

      <div
        className="
          flex
          items-center
          gap-3
          bg-slate-900
          border
          border-slate-800
          rounded-lg
          px-4
          py-2
          w-96
        "
      >

        <Search
          size={18}
          className="text-slate-400"
        />

        <input
          placeholder="Search papers, methods, datasets..."
          className="
            bg-transparent
            outline-none
            text-sm
            w-full
            text-white
            placeholder:text-slate-500
          "
        />

      </div>



      {/* Right Section */}

      <div
        className="
          flex
          items-center
          gap-5
        "
      >

        <button
          className="
            text-slate-400
            hover:text-white
          "
        >
          <Bell size={20}/>
        </button>


        <div
          className="
            flex
            items-center
            gap-2
          "
        >

          <UserCircle
            size={30}
            className="text-indigo-400"
          />


          <span className="
            text-sm
            text-slate-300
          ">
            Researcher
          </span>

        </div>


      </div>


    </header>

  )

}


export default Navbar;